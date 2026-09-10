# Switching 🎮

**Switching** は、Nintendo Switchのブラウザを使ってPCゲームをリモート操作するための、シンプルで軽量なゲームストリーミングシステムです。

PCでゲームを実行し、PC画面をSwitchへストリーミングします。

さらに、Switchのコントローラー入力をPCへ送信し、PC側では仮想ゲームパッドとして認識させます。

```text
        PC
        │
   ┌────▼─────┐
   │ PCゲーム │
   └────┬─────┘
        │
    画面キャプチャ
        │
       JPEG
        │
    WebSocket
        │
        ▼
┌─────────────────┐
│ Switch ブラウザ │
└────────┬────────┘
         │
     Gamepad API
         │
     WebSocket
         │
         ▼
┌─────────────────┐
│ 仮想ゲームパッド │
└────────┬────────┘
         │
         ▼
      PCゲーム
```

つまり、

**PC → Switch：映像**

**Switch → PC：コントローラー**

という双方向通信を行います。

---

# ✨ 特徴

- 🎮 SwitchのブラウザでPCゲームを操作
- 🖥️ PC画面をリアルタイム表示
- 🎮 SwitchコントローラーをPCへ転送
- ⚡ コントローラー入力は約100Hz
- 📺 デフォルト960×540 / 30FPS
- 🖼️ JPEGによるシンプルな映像配信
- 🌐 HTTP + WebSocketのみで動作
- 📱 Switchのタッチ操作にも対応
- 🐧 Linux対応
- 🪟 Windows対応
- 🔌 外部ストリーミングサービス不要

---

# 📁 ファイル構成

```text
Switching/
├── Switching-Linux.py
├── Switching-Win.py
└── README.md
```

## Switching-Linux.py

Linux用です。

仮想ゲームパッドには、

```text
evdev
uinput
```

を使用します。

## Switching-Win.py

Windows用です。

仮想ゲームパッドには、

```text
vgamepad
```

を使用し、Xbox 360互換のXInputコントローラーとして認識させます。

---

# 💻 必要環境

## Linux

### 必要なもの

- Python 3
- mss
- Pillow
- websockets
- evdev
- uinput

Ubuntu / Linux Mintなどでは、

```bash
sudo apt install python3-pip python3-evdev
```

その後、

```bash
pip3 install mss pillow websockets
```

環境によってはシステムPythonへの`pip`インストールが制限されているため、その場合は仮想環境を使用してください。

```bash
python3 -m venv venv
source venv/bin/activate
pip install mss pillow websockets evdev
```

---

# 🪟 Windows

### 必要なもの

- Python 3
- mss
- Pillow
- websockets
- vgamepad

インストール：

```powershell
pip install mss pillow websockets vgamepad
```

---

# ▶️ 起動

## Linux

```bash
python3 Switching-Linux.py
```

または、

```bash
python Switching-Linux.py
```

---

## Windows

```powershell
python Switching-Win.py
```

---

# 🌐 Switchから接続

SwitchとPCを同じネットワークに接続します。

Switchのブラウザから、

```text
http://PCのIPアドレス:8080/
```

へアクセスします。

例えばPCのIPアドレスが、

```text
192.168.0.100
```

の場合：

```text
http://192.168.0.100:8080/
```

です。

Switchingを起動すると、接続用アドレスがターミナルにも表示されます。

```text
=================================================================
 Switching
=================================================================

Open:

http://192.168.0.100:8080/

WebSocket:

ws://192.168.0.100:8081
```

---

# 📡 通信

Switchingでは2つのポートを使用します。

| ポート | 用途 |
|---:|---|
| `8080` | SwitchへWebページを提供 |
| `8081` | 映像・コントローラー通信 |

## HTTP

```text
PC → Switch
```

SwitchingのHTMLページを提供します。

```text
http://PC-IP:8080/
```

## WebSocket

```text
PC ←→ Switch
```

WebSocketでは、

```text
PC → Switch
JPEG映像

Switch → PC
コントローラーJSON
```

を送受信します。

---

# 🖥️ 映像設定

デフォルトでは、

```python
SCREEN_W = 960
SCREEN_H = 540
FPS = 30
JPEG_QUALITY = 65
```

となっています。

つまり、

```text
解像度 : 960 × 540
FPS    : 30
JPEG   : Quality 65
```

です。

---

# ⚙️ 解像度を変更する

例えば1280×720にする場合：

```python
SCREEN_W = 1280
SCREEN_H = 720
```

60FPSにする場合：

```python
FPS = 60
```

画質を上げる場合：

```python
JPEG_QUALITY = 75
```

数値を上げるほど画質は良くなりますが、

- CPU負荷
- エンコード負荷
- 通信量
- Switch側の負荷

も増加します。

---

# 🎮 コントローラー

SwitchingはSwitchのGamepad APIからコントローラー情報を取得します。

対応している入力：

| Switch | PC側 |
|---|---|
| A | A |
| B | B |
| X | X |
| Y | Y |
| L | LB |
| R | RB |
| ZL | 左トリガー |
| ZR | 右トリガー |
| - | Back / Select |
| + | Start |
| L3 | 左スティック押し込み |
| R3 | 右スティック押し込み |
| ↑ | D-Pad Up |
| ↓ | D-Pad Down |
| ← | D-Pad Left |
| → | D-Pad Right |
| 左スティック | 左スティック |
| 右スティック | 右スティック |
| HOME | Home / Guide |

---

# 🖐️ タッチ操作

Switchingにはタッチ操作用のボタンも用意されています。

```text
┌─────┐                                      ┌─────┐
│ ZL  │                                      │ ZR  │
└─────┘                                      └─────┘

                                             ┌─────┐
                                             │  X  │
                                             └─────┘


┌────┐                    ┌────────┐         ┌────┐
│  - │                    │  HOME  │         │ +  │
└────┘                    └────────┘         └────┘
```

現在のタッチボタン：

- ZL
- ZR
- X
- -
- +
- HOME

物理コントローラーがない場合でも、一部の操作が可能です。

また、物理コントローラーとタッチ操作を同時に使用できます。

---

# 🎯 スティック

スティックにはデッドゾーンを設定しています。

```python
DEADZONE = 0.08
```

スティック入力が約8%未満の場合は、

```text
0
```

として扱います。

これにより、スティックの微妙なズレによる勝手な入力を抑えます。

---

# 🐧 Linux版

Linux版：

```text
Switching-Linux.py
```

では`evdev`の`UInput`を使用して仮想ゲームパッドを作成します。

仮想デバイス名：

```text
Switch Browser Virtual Controller
```

確認：

```bash
cat /proc/bus/input/devices
```

または、

```bash
ls /dev/input/
```

`uinput`が読み込まれていない場合：

```bash
sudo modprobe uinput
```

---

# 🪟 Windows版

Windows版：

```text
Switching-Win.py
```

では`vgamepad`を使用します。

```python
ui = vg.VX360Gamepad()
```

これによってWindowsからはXbox 360互換コントローラーとして認識されます。

```text
Switch
   │
   ▼
Gamepad API
   │
   ▼
Switching-Win.py
   │
   ▼
vgamepad
   │
   ▼
Xbox 360 Controller
   │
   ▼
PC Game
```

XInput対応ゲームで利用できます。

---

# 🔥 ファイアウォール

Linuxで`ufw`を使用している場合：

```bash
sudo ufw allow 8080/tcp
sudo ufw allow 8081/tcp
```

確認：

```bash
sudo ufw status
```

---

# 🐛 トラブルシューティング

## Switchからページを開けない

PC側でポートを確認：

```bash
ss -ltnp | grep -E '8080|8081'
```

以下の2ポートが待ち受け状態になっていることを確認してください。

```text
8080
8081
```

---

## 映像が表示されない

Switch側のステータスを確認してください。

正常に接続すると、

```text
WebSocket connected
```

と表示されます。

`WebSocket disconnected`になる場合は、

- PCとSwitchが同じネットワークにいるか
- ファイアウォールが通信を遮断していないか
- PC側のSwitchingが起動しているか

を確認してください。

---

## コントローラーが認識されない

ブラウザの開発者コンソールなどで、

```javascript
navigator.getGamepads()
```

を実行すると、ブラウザが取得しているGamepad情報を確認できます。

---

## Linuxで仮想コントローラーが作成されない

まず、

```bash
sudo modprobe uinput
```

を実行してください。

その後、

```bash
ls -l /dev/uinput
```

を確認します。

---

## Windowsでゲームがコントローラーを認識しない

Windows版ではXbox 360互換のXInputコントローラーを作成します。

ゲーム側がXInputに対応しているか確認してください。

---

# 🚀 パフォーマンス

Switchingはできるだけシンプルな構成になっています。

映像：

```text
画面
 ↓
mss
 ↓
Pillow
 ↓
JPEG
 ↓
WebSocket
 ↓
Switch
```

コントローラー：

```text
Switch Controller
 ↓
Gamepad API
 ↓
WebSocket
 ↓
Python
 ↓
Virtual Gamepad
 ↓
PC Game
```

コントローラーは約10ms間隔、つまり約100Hzで送信します。

また、映像は「最新フレーム」を保持する方式になっているため、古いフレームが大量に蓄積することを避けています。

---

# 🔐 セキュリティ

Switchingは基本的にLAN内での利用を想定しています。

サーバーは、

```text
0.0.0.0:8080
0.0.0.0:8081
```

で待ち受けます。

そのため、同じネットワーク上にいる他の端末からもアクセスできる可能性があります。

インターネットへ直接公開する場合は、認証やHTTPS/WSSなどのセキュリティ対策を追加してください。

---

# 🧩 使用技術

## Linux

- Python 3
- mss
- Pillow
- websockets
- evdev
- uinput

## Windows

- Python 3
- mss
- Pillow
- websockets
- vgamepad
- XInput

## Switch

- HTML
- CSS
- JavaScript
- Gamepad API
- WebSocket API

---

# 🔮 今後追加したい機能

- [ ] 1280×720
- [ ] 60FPS
- [ ] 音声ストリーミング
- [ ] H.264
- [ ] WebCodecs
- [ ] WebRTC
- [ ] フルスクリーン
- [ ] FPS表示
- [ ] ビットレート表示
- [ ] リアルタイム画質変更
- [ ] 仮想タッチスティック
- [ ] タッチボタン配置変更
- [ ] 複数コントローラー
- [ ] HTTPS / WSS
- [ ] 認証
- [ ] 設定画面

---

# 📜 ライセンス

現在、ライセンスは設定されていません。

公開する場合は、用途に合わせて`LICENSE`ファイルを追加してください。

---

# 🎮 Switchingについて

**Switching**は、

> PCゲームをNintendo Switchから操作する

というシンプルな目的のために作られた実験的なストリーミングシステムです。

専用クライアントをSwitchにインストールする必要はありません。

Switchのブラウザからページを開くだけで使用できます。

```text
        SWITCHING

 PC ──────────────→ Switch
       ゲーム映像

 PC ←────────────── Switch
       コントローラー
```

**PCとSwitchをつなぐ、小さなゲームストリーミングシステム。**

🎮 **Switching**