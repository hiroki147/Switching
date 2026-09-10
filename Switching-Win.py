#!/usr/bin/env python3

import asyncio
import io
import json
import socket
import threading
import time
import http.server
import socketserver

import mss
from PIL import Image
import websockets
import vgamepad as vg


# ============================================================
# 設定
# ============================================================

HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8080

WS_HOST = "0.0.0.0"
WS_PORT = 8081


# ============================================================
# 映像
# ============================================================

SCREEN_W = 960
SCREEN_H = 540
FPS = 30
JPEG_QUALITY = 65

# ============================================================
# スティック
# ============================================================

DEADZONE = 0.08


# ============================================================
# コントローラー
# ============================================================

CONTROLLER_INTERVAL = 0.01


# ============================================================
# Virtual Gamepad (Windows XInput)
# ============================================================

ui = vg.VX360Gamepad()


# ============================================================
# 状態
# ============================================================

controller_lock = threading.Lock()

frame_lock = threading.Lock()

last_frame = None


# ============================================================
# Utility
# ============================================================

def clamp(value, minimum, maximum):

    if value < minimum:
        return minimum

    if value > maximum:
        return maximum

    return value


def stick_float(value):

    value = clamp(value, -1.0, 1.0)

    if abs(value) < DEADZONE:
        return 0.0

    if value > 0:
        value = (value - DEADZONE) / (1.0 - DEADZONE)
    else:
        value = (value + DEADZONE) / (1.0 - DEADZONE)

    return clamp(value, -1.0, 1.0)


# ============================================================
# Controller
# ============================================================

button_mapping = {
    # ブラウザ上のGamepad APIインデックス : vgamepad (Xbox360) のボタン
    0: vg.XUSB_BUTTON.XUSB_GAMEPAD_A,              # B相当 (下)
    1: vg.XUSB_BUTTON.XUSB_GAMEPAD_B,              # A相当 (右)
    2: vg.XUSB_BUTTON.XUSB_GAMEPAD_X,              # X相当 (左)
    3: vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,              # Y相当 (上)
    4: vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,  # L
    5: vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER, # R
    8: vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,           # - (Back)
    9: vg.XUSB_BUTTON.XUSB_GAMEPAD_START,          # + (Start)
    10: vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,    # L3
    11: vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,   # R3
    12: vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,       # D-Pad Up
    13: vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,     # D-Pad Down
    14: vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,     # D-Pad Left
    15: vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,    # D-Pad Right
    16: vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,         # Home (Xbox Guide)
}


def send_controller(data):

    buttons = data.get("buttons", [])
    axes = data.get("axes", [])

    with controller_lock:

        # ----------------------------------------------------
        # 通常ボタン
        # ----------------------------------------------------
        for index, xusb_btn in button_mapping.items():
            pressed = False
            if index < len(buttons):
                try:
                    pressed = bool(buttons[index].get("pressed", False))
                except Exception:
                    pressed = False

            if pressed:
                ui.press_button(button=xusb_btn)
            else:
                ui.release_button(button=xusb_btn)

        # ----------------------------------------------------
        # ZL / ZR (アナログ値)
        # ----------------------------------------------------
        ZL_INDEX = 17
        ZR_INDEX = 18

        zl = 0.0
        zr = 0.0

        if len(buttons) > ZL_INDEX:
            try:
                zl = float(buttons[ZL_INDEX].get("value", 0))
            except Exception:
                zl = 0.0

        if len(buttons) > ZR_INDEX:
            try:
                zr = float(buttons[ZR_INDEX].get("value", 0))
            except Exception:
                zr = 0.0

        ui.left_trigger_float(value_float=clamp(zl, 0.0, 1.0))
        ui.right_trigger_float(value_float=clamp(zr, 0.0, 1.0))

        # ----------------------------------------------------
        # スティック
        # ブラウザのGamepad APIではY軸が下方向正(+)のため、
        # XInput (上方向正(+)) に合わせるためY軸の符号を反転(-ly)させます。
        # ----------------------------------------------------
        if len(axes) >= 4:
            lx = float(axes[0])
            ly = float(axes[1])
            rx = float(axes[2])
            ry = float(axes[3])

            ui.left_joystick_float(
                x_value_float=stick_float(lx),
                y_value_float=-stick_float(ly)
            )

            ui.right_joystick_float(
                x_value_float=stick_float(rx),
                y_value_float=-stick_float(ry)
            )

        ui.update()


# ============================================================
# Screen Capture
# ============================================================

sct = mss.mss()

monitor = sct.monitors[1]


source_w = monitor["width"]
source_h = monitor["height"]


target_ratio = (
    SCREEN_W /
    SCREEN_H
)

source_ratio = (
    source_w /
    source_h
)


if source_ratio > target_ratio:

    crop_w = int(
        source_h *
        target_ratio
    )

    crop_left = (
        source_w -
        crop_w
    ) // 2

    crop_top = 0

    crop_right = (
        crop_left +
        crop_w
    )

    crop_bottom = source_h


elif source_ratio < target_ratio:

    crop_h = int(
        source_w /
        target_ratio
    )

    crop_left = 0

    crop_top = (
        source_h -
        crop_h
    ) // 2

    crop_right = source_w

    crop_bottom = (
        crop_top +
        crop_h
    )


else:

    crop_left = 0
    crop_top = 0
    crop_right = source_w
    crop_bottom = source_h


# ============================================================
# Capture Thread
# ============================================================

def capture_screen():

    global last_frame

    frame_interval = (
        1.0 /
        FPS
    )

    next_frame_time = (
        time.perf_counter()
    )

    while True:

        now = time.perf_counter()

        if now < next_frame_time:

            time.sleep(
                next_frame_time -
                now
            )

        next_frame_time += frame_interval


        try:

            # ------------------------------------------------
            # Capture
            # ------------------------------------------------

            raw = sct.grab(
                monitor
            )


            # ------------------------------------------------
            # RGB
            # ------------------------------------------------

            img = Image.frombytes(
                "RGB",
                raw.size,
                raw.rgb
            )


            # ------------------------------------------------
            # Crop
            # ------------------------------------------------

            if (
                crop_left != 0
                or
                crop_top != 0
                or
                crop_right != source_w
                or
                crop_bottom != source_h
            ):

                img = img.crop(
                    (
                        crop_left,
                        crop_top,
                        crop_right,
                        crop_bottom
                    )
                )


            # ------------------------------------------------
            # Resize
            # ------------------------------------------------

            if (
                img.width != SCREEN_W
                or
                img.height != SCREEN_H
            ):

                img = img.resize(
                    (
                        SCREEN_W,
                        SCREEN_H
                    ),
                    Image.Resampling.BOX
                )


            # ------------------------------------------------
            # JPEG
            # ------------------------------------------------

            buf = io.BytesIO()

            img.save(
                buf,
                format="JPEG",
                quality=JPEG_QUALITY,
                optimize=False,
                progressive=False
            )

            frame = buf.getvalue()


            # ------------------------------------------------
            # 最新フレーム
            # ------------------------------------------------

            with frame_lock:

                last_frame = frame


        except Exception as ex:

            print(
                "capture error:",
                ex
            )

            time.sleep(
                0.05
            )


threading.Thread(
    target=capture_screen,
    daemon=True
).start()


# ============================================================
# HTML
# ============================================================

HTML = r"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="
        width=device-width,
        height=device-height,
        initial-scale=1,
        minimum-scale=1,
        maximum-scale=1,
        user-scalable=no
    "
>

<title>Switch PC Stream</title>

<style>

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

html,
body {

    width: 100%;
    height: 100%;

    overflow: hidden;

    background: #000;

    user-select: none;
    -webkit-user-select: none;

    -webkit-touch-callout: none;

    touch-action: none;

    overscroll-behavior: none;
}

#screen {

    position: fixed;

    left: 0;
    top: 0;

    width: 100vw;
    height: 100vh;

    object-fit: contain;

    object-position: center center;

    display: block;

    pointer-events: none;

    user-select: none;

    -webkit-user-drag: none;

    -webkit-user-select: none;
}

#capture {

    position: fixed;

    left: 0;
    top: 0;

    width: 1px;
    height: 1px;

    opacity: 0;

    outline: none;

    pointer-events: none;
}

#status {

    position: fixed;

    left: 5px;
    top: 5px;

    padding: 4px 7px;

    color: white;

    background:
        rgba(
            0,
            0,
            0,
            0.60
        );

    font-family: monospace;

    font-size: 11px;

    z-index: 1000;

    pointer-events: none;

    opacity: 0.35;
}

#touch-overlay {
    position: fixed;
    left: 0;
    top: 0;
    width: 100vw;
    height: 100vh;
    pointer-events: none;
    z-index: 900;
}

.touch-btn {
    position: absolute;
    pointer-events: auto;
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.35);
    color: white;
    font-family: monospace;
    font-size: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    user-select: none;
    -webkit-user-select: none;
    touch-action: none;
}

.touch-btn.active {
    background: rgba(255,255,255,0.35);
}

.tb-zl    { left: 10px;  top: 10px; }
.tb-zr    { right: 10px; top: 10px; }
.tb-x     { right: 10px; top: 84px; width: 56px; height: 56px; border-radius: 12px; }
.tb-minus { left: 10px;  bottom: 20px; width: 48px; height: 48px; border-radius: 12px; }
.tb-plus  { right: 10px; bottom: 20px; width: 48px; height: 48px; border-radius: 12px; }
.tb-home  { left: 50%; bottom: 16px; transform: translateX(-50%); width: 52px; height: 52px; border-radius: 50%; font-size: 11px; }

</style>

</head>

<body>

<div
    id="capture"
    tabindex="-1">
</div>

<img
    id="screen"
    draggable="false"
    alt=""
>

<div id="status">
    Connecting...
</div>

<!-- タッチオーバーレイボタン -->
<div id="touch-overlay">
    <div class="touch-btn tb-zl"  data-btn="17">ZL</div>
    <div class="touch-btn tb-zr"  data-btn="18">ZR</div>
    <div class="touch-btn tb-x"   data-btn="3">X</div>
    <div class="touch-btn tb-minus" data-btn="8">-</div>
    <div class="touch-btn tb-plus"  data-btn="9">+</div>
    <div class="touch-btn tb-home"  data-btn="16">HOME</div>
</div>


<script>


// ============================================================
// Elements
// ============================================================

const screen =
    document.getElementById(
        "screen"
    );

const statusElement =
    document.getElementById(
        "status"
    );


function setStatus(text) {

    statusElement.textContent =
        text;

}


// ============================================================
// NX Button
// ============================================================

const NX =
    window.nx;

const nxAvailable = !!(
    NX &&
    NX.footer &&
    typeof NX.footer.setAssign ===
        "function"
);


function setupNXButton(button) {

    if (!nxAvailable) {

        return;
    }

    try {

        NX.footer.setAssign(

            button,

            "PC",

            function () {

                /*
                 * Gamepad APIで取得するので
                 * ブラウザ標準動作だけ抑制。
                 */

            },

            {
                se:
                    "SeWebBtnDecide"
            }

        );

    } catch (error) {

        console.log(
            "NX setAssign failed:",
            button,
            error
        );

    }

}


setupNXButton("A");
setupNXButton("B");
setupNXButton("X");
setupNXButton("Y");


// ============================================================
// Focus
// ============================================================

function captureFocus() {

    try {

        const capture =
            document.getElementById(
                "capture"
            );

        if (capture) {

            capture.focus();

        }

    } catch (e) {}

}


captureFocus();


document.addEventListener(
    "click",
    captureFocus,
    true
);


document.addEventListener(
    "touchstart",
    captureFocus,
    true
);


// ============================================================
// Browser Back対策
// ============================================================

try {

    history.pushState(
        null,
        "",
        location.href
    );

    window.addEventListener(
        "popstate",
        function () {

            try {

                history.pushState(
                    null,
                    "",
                    location.href
                );

            } catch (e) {}

        }
    );

} catch (e) {}


// ============================================================
// WebSocket
// ============================================================

let ws = null;


function connectWebSocket() {

    const host =
        location.hostname;

    ws = new WebSocket(
        "ws://" +
        host +
        ":8081/"
    );


    /*
     * JPEGはBlob
     */

    ws.binaryType =
        "blob";


    ws.onopen = function () {

        setStatus(
            "WebSocket connected"
        );

        console.log(
            "WebSocket connected"
        );

    };


    ws.onclose = function () {

        setStatus(
            "WebSocket disconnected"
        );

        console.log(
            "WebSocket disconnected"
        );


        setTimeout(
            connectWebSocket,
            1000
        );

    };


    ws.onerror = function (error) {

        console.log(
            "WebSocket error",
            error
        );

    };


    ws.onmessage = function (event) {

        /*
         * サーバーから来るのはJPEGだけ
         */

        if (
            typeof event.data ===
                "string"
        ) {

            return;

        }


        const url =
            URL.createObjectURL(
                event.data
            );


        screen.onload =
            function () {

                URL.revokeObjectURL(
                    url
                );

            };


        screen.src =
            url;

    };

}


connectWebSocket();


// ============================================================
// Gamepad
// ============================================================

let gamepad = null;


function findGamepad() {

    try {

        if (
            !navigator.getGamepads
        ) {

            return null;

        }

        const pads =
            navigator.getGamepads();


        for (
            let i = 0;
            i < pads.length;
            i++
        ) {

            if (pads[i]) {

                return pads[i];

            }

        }

    } catch (e) {}

    return null;
}


// ============================================================
// Connected
// ============================================================

window.addEventListener(
    "gamepadconnected",
    function (event) {

        gamepad =
            event.gamepad;

        console.log(
            "Gamepad connected:",
            gamepad.id
        );

    }
);


window.addEventListener(
    "gamepaddisconnected",
    function (event) {

        if (
            gamepad &&
            event.gamepad.index ===
                gamepad.index
        ) {

            gamepad = null;

        }

    }
);


// ============================================================
// Gamepad → WebSocket
// ============================================================

// ============================================================
// タッチオーバーレイ（ZL/ZR/X/-/+/Home 用）
// ============================================================

const touchOverride = {}; // { buttonIndex: true/false }

document.querySelectorAll(".touch-btn").forEach(function (el) {

    const idx = parseInt(el.dataset.btn, 10);

    function setPressed(pressed) {
        touchOverride[idx] = pressed;
        el.classList.toggle("active", pressed);
    }

    el.addEventListener("touchstart", function (ev) {
        ev.preventDefault();
        setPressed(true);
    }, { passive: false });

    el.addEventListener("touchend", function (ev) {
        ev.preventDefault();
        setPressed(false);
    }, { passive: false });

    el.addEventListener("touchcancel", function (ev) {
        ev.preventDefault();
        setPressed(false);
    }, { passive: false });

    // マウスでのテスト用（PCブラウザ確認時に便利）
    el.addEventListener("mousedown", function () { setPressed(true); });
    el.addEventListener("mouseup", function () { setPressed(false); });
    el.addEventListener("mouseleave", function () { setPressed(false); });
});

let lastStatusTime = 0;


function pollGamepad() {

    const found =
        findGamepad();


    if (found) {

        gamepad =
            found;

    }


    const hasTouchInput =
        Object.keys(touchOverride).some(
            function (k) { return touchOverride[k]; }
        );

    if (
        (gamepad || hasTouchInput) &&
        ws &&
        ws.readyState ===
            WebSocket.OPEN
    ) {

        const buttons = [];

        if (gamepad) {

            for (
                let i = 0;
                i < gamepad.buttons.length;
                i++
            ) {

                const b =
                    gamepad.buttons[i];


                buttons.push({

                    pressed:
                        !!b.pressed,

                    value:
                        Number(
                            b.value || 0
                        )

                });

            }

        }


        // ----------------------------------------------------
        // タッチオーバーレイの入力をbuttonsに合成
        // ----------------------------------------------------

        for (const idxStr in touchOverride) {

            const idx = parseInt(idxStr, 10);

            if (touchOverride[idx]) {

                while (buttons.length <= idx) {
                    buttons.push({ pressed: false, value: 0 });
                }

                buttons[idx] = { pressed: true, value: 1 };
            }
        }


        const axes = [];


        if (gamepad) {

            for (
                let i = 0;
                i < gamepad.axes.length;
                i++
            ) {

                axes.push(
                    Number(
                        gamepad.axes[i] || 0
                    )
                );

            }

        }


        // ----------------------------------------------------
        // Status
        // ----------------------------------------------------

        const now =
            performance.now();


        if (
            now - lastStatusTime > 500
        ) {

            lastStatusTime =
                now;

            if (axes.length >= 4) {

                setStatus(

                    "WS OK | " +

                    "LX " +
                    axes[0].toFixed(2) +

                    " LY " +
                    axes[1].toFixed(2) +

                    " RX " +
                    axes[2].toFixed(2) +

                    " RY " +
                    axes[3].toFixed(2) +

                    (hasTouchInput ? " | TOUCH" : "")

                );

            } else if (hasTouchInput) {

                setStatus(
                    "WS OK | TOUCH ONLY (no gamepad)"
                );

            } else {

                setStatus(
                    "WS OK | no input"
                );

            }

        }


        // ----------------------------------------------------
        // JSON送信
        // ----------------------------------------------------

        try {

            ws.send(
                JSON.stringify({

                    type:
                        "gamepad",

                    buttons:
                        buttons,

                    axes:
                        axes

                })
            );

        } catch (e) {}

    }


    setTimeout(
        pollGamepad,
        10
    );

}


pollGamepad();


// ============================================================
// Browser操作抑制
// ============================================================

function preventBrowserNavigation(event) {

    try {

        event.preventDefault();

    } catch (e) {}

}


document.addEventListener(
    "wheel",
    preventBrowserNavigation,
    {
        passive: false,
        capture: true
    }
);


document.addEventListener(
    "gesturestart",
    preventBrowserNavigation,
    {
        passive: false,
        capture: true
    }
);


document.addEventListener(
    "gesturechange",
    preventBrowserNavigation,
    {
        passive: false,
        capture: true
    }
);


document.addEventListener(
    "gestureend",
    preventBrowserNavigation,
    {
        passive: false,
        capture: true
    }
);


// ============================================================
// キー操作抑制
// ============================================================

document.addEventListener(
    "keydown",
    function (event) {

        const blockedKeys = [

            "ArrowUp",
            "ArrowDown",
            "ArrowLeft",
            "ArrowRight",

            "PageUp",
            "PageDown",

            "Home",
            "End"

        ];


        if (
            blockedKeys.indexOf(
                event.key
            ) !== -1
        ) {

            try {

                event.preventDefault();

            } catch (e) {}

        }

    },
    true
);

</script>

</body>

</html>
"""


# ============================================================
# HTTP Server
# ============================================================

class Handler(
    http.server.BaseHTTPRequestHandler
):

    def do_GET(self):

        if self.path == "/":

            data = HTML.encode(
                "utf-8"
            )

            self.send_response(200)

            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8"
            )

            self.send_header(
                "Content-Length",
                str(len(data))
            )

            self.end_headers()

            self.wfile.write(data)

            return


        self.send_response(404)

        self.end_headers()


    def log_message(
        self,
        format,
        *args
    ):

        return


# ============================================================
# WebSocket
# ============================================================

async def websocket_handler(
    websocket,
    path=None
):

    print()
    print(
        "================================"
    )
    print(
        " Switch connected!"
    )
    print(
        "================================"
    )
    print()


    async def send_frames():

        frame_interval = (
            1.0 /
            FPS
        )


        while True:

            with frame_lock:

                frame = last_frame


            if frame is not None:

                try:

                    await websocket.send(
                        frame
                    )

                except Exception:

                    return


            await asyncio.sleep(
                frame_interval
            )


    async def receive_controller():

        try:

            async for message in websocket:

                # --------------------------------------------
                # JPEGはPC→Switchのみ
                # --------------------------------------------

                if isinstance(
                    message,
                    bytes
                ):

                    continue


                # --------------------------------------------
                # Gamepad JSON
                # --------------------------------------------

                try:

                    data = json.loads(
                        message
                    )

                except Exception:

                    continue


                if data.get(
                    "type"
                ) != "gamepad":

                    continue


                try:

                    send_controller(
                        data
                    )

                except Exception as ex:

                    print(
                        "controller error:",
                        ex
                    )

        except Exception:

            return


    try:

        await asyncio.gather(

            send_frames(),

            receive_controller()

        )

    except Exception:

        pass


    print(
        "Switch disconnected"
    )


# ============================================================
# WebSocket Server Thread
# ============================================================

def run_websocket():

    async def main():

        print(
            f"WebSocket: "
            f"ws://0.0.0.0:{WS_PORT}"
        )

        async with websockets.serve(

            websocket_handler,

            WS_HOST,

            WS_PORT,

            max_size=None

        ):

            await asyncio.Future()


    asyncio.run(
        main()
    )


# ============================================================
# Local IP
# ============================================================

def get_local_ip():

    try:

        s = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        s.connect(
            (
                "8.8.8.8",
                80
            )
        )

        ip = s.getsockname()[0]

        s.close()

        return ip

    except Exception:

        return "127.0.0.1"


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    ip = get_local_ip()


    print()
    print("=" * 65)
    print(
        " Switch PC Streaming Controller (Windows/vgamepad)"
    )
    print("=" * 65)
    print()

    print(
        "Open:"
    )

    print()

    print(
        f"http://{ip}:{HTTP_PORT}/"
    )

    print()

    print(
        "WebSocket:"
    )

    print(
        f"ws://{ip}:{WS_PORT}"
    )

    print()

    print(
        "Video:"
    )

    print(
        f"  {SCREEN_W}x{SCREEN_H}"
    )

    print(
        f"  {FPS} FPS"
    )

    print(
        f"  JPEG Q={JPEG_QUALITY}"
    )

    print()

    print(
        "Controller:"
    )

    print(
        "  A/B/X/Y"
    )

    print(
        "  L/R"
    )

    print(
        "  ZL/ZR"
    )

    print(
        "  D-Pad"
    )

    print(
        "  L Stick"
    )

    print(
        "  R Stick"
    )

    print(
        "  -/+"
    )

    print(
        "  L3/R3"
    )

    print()

    print(
        "Controller polling: ~100Hz"
    )

    print()

    print(
        "Virtual controller:"
    )

    print(
        "  Windows XInput (Xbox 360 Controller)"
    )

    print()

    print("=" * 65)
    print()


    # --------------------------------------------------------
    # WebSocket開始
    # --------------------------------------------------------

    threading.Thread(
        target=run_websocket,
        daemon=True
    ).start()


    # --------------------------------------------------------
    # HTTP開始
    # --------------------------------------------------------

    server = socketserver.ThreadingTCPServer(
        (
            HTTP_HOST,
            HTTP_PORT
        ),
        Handler
    )

    server.daemon_threads = True

    print(
        f"HTTP server: "
        f"http://{ip}:{HTTP_PORT}/"
    )

    print()

    try:

        server.serve_forever()

    except KeyboardInterrupt:

        print()
        print(
            "Stopping..."
        )

    finally:

        server.shutdown()
        ui.reset()
        ui.update()
