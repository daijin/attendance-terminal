# RC-S300 打刻端末

Raspberry Pi 3B、Sony RC-S300、DS1307を使う、オフライン優先の打刻システムです。カードのUID（FeliCaではIDm）と時刻のみを端末内SQLiteに保存し、起動時にオンラインならGoogleスプレッドシートへ未送信分をアップロードします。氏名との突合せは行いません。

## 設計

```text
RC-S300 ─PC/SC─> Python常駐プロセス ─> SQLite (常に先に保存)
                              └─オンライン起動時─HTTPS─> Apps Script ─> Sheet
DS1307 ──> system clock             再送・UUID重複排除
```

- 端末内DBへの保存が成功してから成功音を鳴らします。
- 同じUIDを3秒以内に再検出した場合は保存しません。カードを置いたままにしても1回です。
- 各レコードにUUIDを付け、通信切断後の再送や複数端末からのアップロードでもApps Script側で重複を除きます。
- アップロード成功応答を受けた行だけを送信済みにします。DBの行は削除しません。
- 起動時にインターネットへ到達できればアップロードモード、できなければ打刻専用モードです。仕様どおり、その起動中にモードは切り替えません。

## 1. ハードウェア

RC-S300はUSBへ接続します。`nfcpy`はRC-S300非対応なので、本実装はPC/SCを使用します。

DS1307（一般的なモジュール）の配線:

| DS1307 | Raspberry Pi 3B | 物理ピン |
|---|---|---:|
| VCC | 5V | 2 または 4 |
| GND | GND | 6 |
| SDA | GPIO2 / SDA1 | 3 |
| SCL | GPIO3 / SCL1 | 5 |

モジュールのI2Cプルアップが5Vへ接続されている製品をGPIOへ直結してはいけません。3.3V対応品であることを回路図・仕様書で確認してください。

通知部品を使わない場合は設定のGPIOをすべて`null`にできます。追加購入しない方法として、Raspberry Pi 3Bの3.5mm端子へ手持ちのイヤホンまたはアンプ内蔵スピーカーを接続し、WAVを再生できます。RC-S300内蔵LEDはカードとの通信時に自動点灯しますが、端末から任意の色・パターンを指定する用途には使えません。

GPIOを使う場合のおすすめは、抵抗・トランジスタを内蔵した「3.3V対応アクティブブザーモジュール」をメス-メスのジャンパ線で接続する方法です。裸のブザーをGPIOへ直接接続しないでください。オンライン/オフライン表示には抵抗内蔵LEDモジュール2個、または2色LEDモジュールを使えます。

デフォルトの音の意味:

- OS起動時1回: 打刻専用（オフライン）
- OS起動時2回: アップロードモード
- 短く1回: 保存成功
- 3回: GPIO通知系のエラー用途

3秒以内の重複打刻は記録せず、通知音も鳴らしません。systemdによるプロセス再起動時もモード音は再度鳴らさず、`/run`が初期化されるOS再起動時だけ鳴らします。

RC-S300自身のLEDはカード通信状態を示しますが、任意の起動モード表示には使えないため、モード表示は外付けLEDが確実です。

ラズパイ基板上のLEDについては、赤いPWR LEDは電源状態表示、緑のACT LEDは通常SDカードアクセス表示です。ACT LEDをLinuxのsysfs経由で一時的に流用すること自体は可能ですが、機種・OSによって名前や権限が変わり、ストレージアクセス表示も失われます。ケース内では見えにくいため、本システムの運用通知には採用していません。

### 追加購入なしのMP3通知

短いMP3ファイルを配置します。打刻処理を長時間止めないよう、1秒未満の効果音を推奨します。

```bash
sudo cp beep.mp3 /etc/attendance-terminal/sounds/beep.mp3
sudo chown root:attendance /etc/attendance-terminal/sounds/beep.mp3
sudo chmod 0640 /etc/attendance-terminal/sounds/beep.mp3
```

`config.json`を次のようにします。

```json
"buzzer_pin": null,
"notification_sound": "/etc/attendance-terminal/sounds/beep.mp3",
"audio_device": "sysdefault:CARD=Headphones",
"audio_volume_percent": 70
```

`audio_volume_percent`はMP3再生に対するソフトウェア音量で、`0`から`100`まで指定できます。まず`50`程度から試し、必要に応じて調整してください。イヤホン使用時にいきなり`100`で試さないでください。

TrixieではPipeWireがデスクトップ音声を管理しますが、本システムはログインセッションを持たないsystemdサービスなので、ALSAの3.5mm端子へ直接出力します。先にデバイス名を確認します。

```bash
aplay -l
aplay -L | grep -E '^(sysdefault|default)'
sudo -u attendance mpg123 -q -a 'sysdefault:CARD=Headphones' -f 22938 /etc/attendance-terminal/sounds/beep.mp3
```

上の`-f 22938`は約70%です。`mpg123`の基準値は32768が100%で、本システムが設定値から自動計算します。

3.5mm端子から鳴らない場合は、`sudo raspi-config`の音声出力設定でHeadphones（Analog）を選択します。実際のカード名が異なる場合は、`aplay -L`に表示された`sysdefault:`名を`audio_device`へ設定してください。イヤホンは接続できますが、端子はスピーカーレベル出力ではないため、一般的なパッシブスピーカーでは十分な音量が出ません。

端末全体のアナログ出力レベルは`alsamixer`でも調整できます。`F6`でHeadphonesカードを選択し、左右キーで出力、上下キーで音量を変更します。通常はハードウェア側を一度設定し、日常の調整には`audio_volume_percent`を使う方が安全です。

## 2. Raspberry Pi OS Trixie 64-bitの準備

本手順とインストーラーは、クリーンインストールしたRaspberry Pi OS Trixie 64-bit（arm64）を対象にします。OS付属Pythonへ直接`pip install`せず、専用venvを`/opt/attendance-terminal/venv`に作成します。

まずOSを更新します。Trixieでは`sudo`時にパスワード入力を求められる構成があります。

```bash
sudo apt update
sudo apt full-upgrade
sudo reboot
```

I2Cを有効にし、Trixieで使われる`/boot/firmware/config.txt`へ次を追記します。3.5mm音声端子を使うため、既存の`dtparam=audio=on`も有効であることを確認します。

```ini
dtparam=i2c_arm=on
dtoverlay=i2c-rtc,ds1307
dtparam=audio=on
```

再起動後に確認します。

```bash
ls -l /dev/rtc*
sudo hwclock --show
```

初回だけ正しい時刻をRTCへ保存します（ネット接続済みでNTP同期後に実行）。

```bash
timedatectl status
sudo hwclock --systohc --utc
```

`fake-hwclock`が入っていれば、実RTCとの競合を避けるため無効化します。ユニットが存在しないという表示だけなら問題ありません。

```bash
sudo systemctl disable --now fake-hwclock.service
```

NICTを優先NTPにする場合、`/etc/systemd/timesyncd.conf.d/attendance.conf`を作ります。

```ini
[Time]
NTP=ntp.nict.jp
FallbackNTP=time.cloudflare.com
```

反映は `sudo systemctl restart systemd-timesyncd` です。付属の`attendance-clock.service`は、オンライン起動ならNTP同期を最大60秒待ってRTCへ書き、オフラインなら起動時にRTCからシステム時計へ1度だけ読み込みます。

## 3. Googleスプレッドシート

スプレッドシートを作り、`拡張機能` → `Apps Script`を開き、[google_apps_script/Code.gs](google_apps_script/Code.gs)を貼り付けます。

1. Apps Scriptの「プロジェクトの設定」→「スクリプト プロパティ」に `UPLOAD_SECRET` を追加し、十分長いランダム文字列を設定します。
2. `デプロイ` → `新しいデプロイ` → `ウェブアプリ`を選択します。
3. 実行ユーザーは「自分」、アクセスできるユーザーは「全員（匿名ユーザーを含む）」にします。
4. `/exec`で終わるURLを控えます。`/dev` URLは本番用ではありません。

シートそのものを「リンクを知る全員が編集可」にする必要はありません。WebアプリURLを知る第三者からの書込みを防ぐのが共有シークレットです。Apps Scriptのコードを更新したら、新バージョンを作り既存デプロイを更新します。

## 4. インストール

このディレクトリをラズパイへコピーし、次を実行します。

```bash
chmod +x install.sh
sudo ./install.sh
sudoedit /etc/attendance-terminal/config.json
```

最低限、次を端末ごとに変更します。

- `device_id`: 全端末で重複しない名前
- `upload_url`: Apps Scriptの`/exec` URL
- `upload_secret`: スクリプトプロパティと同じ値

GPIOを使う例（BCM番号）は、ブザーをGPIO17、緑LEDをGPIO27、赤LEDをGPIO22にして、それぞれの設定値を `17`, `27`, `22` にします。部品の仕様に従って配線してください。

設定後に再起動します。

```bash
sudo reboot
```

## 5. 動作確認・保守

```bash
pcsc_scan
systemctl status pcscd.socket
sudo systemctl status attendance-terminal
sudo journalctl -u attendance-terminal -f
sudo journalctl -u attendance-clock -b
```

Trixieの`pcscd`は必要時にsocket activationで起動するため、常時稼働プロセスが見えなくても`pcscd.socket`がactiveなら正常です。

未送信件数の確認:

```bash
sudo sqlite3 /var/lib/attendance-terminal/punches.sqlite3 \
  'SELECT COUNT(*) FROM punches WHERE uploaded_at IS NULL;'
```

設定ファイルには共有シークレットがあるため、権限を`root:attendance 0640`のままにします。DBの定期バックアップ、端末ごとに異なるシークレット、Apps Script側で端末別シークレットを管理する拡張も検討してください。

## テスト

開発PCで次を実行します（NFC機器は不要です）。

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest
```
