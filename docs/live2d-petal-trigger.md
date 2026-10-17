# 頭を振ると花びらが散るローカル補助ツール

`tools/vts-petal-trigger.mjs` はVTube Studioの顔トラッキング値を読み、頭の素早い往復を検出して花びらのアニメーションを一度再生する。頭の花を残すため、動かすのは花びら専用パラメータだけにする。モデル側には、落下・回転・消失・非表示での初期位置への復帰を含む `PetalScatter.motion3.json` と、そのアニメーションを一度再生するホットキーが必要。

頭の角度をそのまま落下量にすると、顔を戻したときに花びらも上へ戻ってしまう。この補助ツールは頭振りをきっかけに時間方向のアニメーションを開始する。通常の表情、まばたき、物理演算の出力値は書き換えない。

## 初回設定

Node.js 22以降を使用する。VTSとの通信には `ws` 8.22.0を固定して使う。リポジトリのルートで次を一度実行する。

```shell
npm ci --prefix tools/vts-petal-trigger --ignore-scripts --omit=optional
```

依存はこのツール専用のディレクトリへ入り、バージョンと整合性は同ディレクトリのlockfileで固定される。VTube StudioのプラグインAPIを有効にし、対象モデルで「アニメーションを再生」のホットキーを作り、`PetalScatter.motion3.json` を指定する。キーボードの割り当ては不要。同じファイルを再生するホットキーは一つにする。

Windows PowerShellの例:

```powershell
node .\tools\vts-petal-trigger.mjs --model-name Revenant_Polished --motion-file PetalScatter.motion3.json --token-file "$env:LOCALAPPDATA\RevenantPetals\token.json" --authorize
```

初回だけ、VTube Studioで `Petal Scatter Trigger` / `Pui Local Tools` の接続を許可する。トークンは指定した私有ファイルに保存され、画面やログへ出力されない。既存の別プラグイン用トークンは流用しない。以後は同じコマンドから `--authorize` を外して実行できる。トークンをGitや配布ZIPへ入れない。

モデル名はVTube Studio APIの `modelName` と完全一致させる。VTSが別のPCにある場合は `--host`、ポートを変更している場合は `--port` を指定する。既定の接続先は同じPCの `127.0.0.1:8001`。

## 動作と調整

- 頭のX/Z角度の速度と、9度以上動いた後の反転を検出する。既定の最小速度は毎秒70度、往復の検出時間は1秒。
- 顔検出が750ミリ秒続いてから有効になる。追跡消失、800ミリ秒を超える取得の遅延、モデル切替、再接続時は検出履歴を破棄する。追跡復帰時の角度の飛びを頭振りと誤認しない。実際の取得間隔から速度を計算するため、VTSの応答が毎回67ミリ秒であることは前提にしない。遅延の上限は `--max-gap-ms` で調整できる。
- 再生間隔は最低4.5秒。再生中の頭振りをキューへ積まない。アニメーションが長い場合は `--cooldown-ms` を長くする。
- 対象モデルが読み込まれ、顔検出が有効なときだけ動く。実行直前にもモデルIDと顔検出を再確認する。別モデルのホットキーは呼ばない。
- `--dry-run` でアニメーションを再生せず検出を確認できる。反応しにくい場合は `--velocity 55 --excursion 7`、過敏な場合は `--velocity 95 --excursion 12` などで調整する。
- 接続が切れた場合は自動で再接続する。認証拒否では終了する。VTSから許可を取り消した後は、私有トークンファイルを削除し、`--authorize` で許可し直す。

自動で散らすにはこの補助ツールを起動しておく必要がある。停止していてもモデルの通常のトラッキングや物理演算は使え、VTSのアニメーションホットキーから手動再生できる。Windowsではユーザー用のスタートアップからNodeを窓なしで起動すると毎回手動で起動する手間を省ける。スタートアップの登録先とトークンは各利用者のローカル設定として扱う。

リポジトリ外へ配置する場合は、`vts-petal-trigger.mjs` と同じディレクトリに `node_modules/ws` を置く方法でも動く。配布時は `ws` に含まれるMITの `LICENSE` を保持する。Node標準WebSocketへはフォールバックしない。Windows Node24とVTSの実機組み合わせでは標準WebSocketの一部リクエストが空フレーム応答になり、同じ条件の `ws` では正常に応答することを確認したため。

カメラ映像・スクリーンショットは取得せず、頭角度も記録しない。ログは接続状態と発火の有無だけを出力する。

## 確認方法

自動テストは `npm test --prefix tools/vts-petal-trigger` で実行する。検出器、対象モデル・顔検出のガード、通信のタイムアウトを検査する。本人の表情・頭振りの認識精度は、次の実操作で別に確認する。

1. 対象モデルで750ミリ秒以上静止し、通常のゆっくりした顔向けで再生しないことを確認する。
2. 頭を左右に素早く振り、花を残して花びらだけが一度落下することを確認する。
3. 頭を連続して振っても、4.5秒より短い間隔で再生しないことを確認する。
4. カメラから顔を外し、再び映った直後は再生しないことを確認する。
5. 別モデルへの切替とVTSの再起動で誤発火しないことを確認する。

## 参照した公式API

- [トラッキング値、顔検出、モデル情報、ホットキー実行](https://github.com/DenchiSoft/VTubeStudio/blob/master/README.md)
- [VTSのホットキーとアニメーション再生](https://github.com/DenchiSoft/VTubeStudio/wiki/VTS-Model-Settings)
- [アニメーション・トラッキング・物理演算の優先順位](https://github.com/DenchiSoft/VTubeStudio/wiki/Interaction-between-Animations%2C-Tracking%2C-Physics%2C-etc.)
- [wsの使用方法とMITライセンス](https://github.com/websockets/ws)、[固定した8.22.0のリリース](https://github.com/websockets/ws/releases/tag/8.22.0)
