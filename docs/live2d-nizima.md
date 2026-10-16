# PSDからnizima LIVE用モデルへ

レイヤー付きPSDをそのままnizima LIVEへ渡すことはできません。メッシュと変形キーを作成し、実体のある `.moc3`、`.model3.json`、参照するPNGを一緒に用意します。本手順の画像・PSD・個人モデルはローカルに保持し、Gitには含めません。

## 使用した環境

- [PSD2Live](https://github.com/tsunehimatoi/psd2live) v3.4.5 Linux x64。配布版に同梱のJavaを使用。
- 編集・保存・書き出しは同アプリのローカルMCPインターフェース。
- 検証はインストール済みCubism Editorの公式Java Native Core。第三者実装の読込成功だけでは互換性の根拠にしません。
- nizima LIVE 2.6.4。出力対象はCubism 5.0。

公式の操作説明は [nizima LIVEへのモデル追加](https://docs.nizimalive.com/tutorials/how-to-add-live2d-model/) と [Cubismの組み込み用データ書き出し](https://docs.live2d.com/cubism-editor-manual/export-moc3-motion3-files/) を参照してください。

## 素材の準備

原本を保持し、コピー側で分類用のレイヤー名を設定します。画面左の目・腕はキャラクター自身の右なので `R`、画面右は `L` です。PSD2Liveの分類器に「画面左」をそのまま渡すと左右が確定しません。

| 素材 | 分類 |
| --- | --- |
| 顔の肌土台 | `face` |
| 白目・瞳・上まぶた | `eyewhite R/L`、`iris R/L`、`eyelash R/L` |
| 下まぶたと肌 | `facedetail lower eyelid R/L` |
| 口内・上歯・舌 | `mouth`、`tooth-t`、`tongue` |
| 上下の唇と肌 | `facedetail upper/lower lip` |
| 前髪・後ろ髪・襟足 | `front hair`、`back hair` |
| 首の肌・茨・接触影 | `neck` を接頭辞にする |
| 衣装と胴体上の装飾 | `topwear` を接頭辞にする |
| 腕・腕の装飾・茨 | `handwear` を接頭辞にし、対応する `R/L` を付ける |

首の茨と影を髪へ分類しないでください。上下のまぶたを両方 `eyelash` にすると、下まぶたにも上まぶた用の閉眼変形が入ります。分類用コピーは保存し直した後、全レイヤーの座標とRGBA画素ハッシュを原本と照合します。

## 生成と調整

LinuxのCLIを使う場合の基本形です。実変換は画像処理の初期化でX11を必要とするため、ディスプレイ接続がない環境では `xvfb-run` を付けます。

```bash
xvfb-run -a /path/to/PSD2Live/bin/PSD2Live \
  --input /path/to/prepared.psd \
  --output /path/to/model-output \
  --lang ja --atlas 4096 --mesh-spacing 40
```

CLI生成だけで完成とは扱わず、編集画面またはローカルMCPで初期姿勢・目・口・顔・髪・胴体を確認します。今回の素材では次を調整しました。

- 頭の変形強度0.45、体0.35。髪の揺れと呼吸も控えめに設定。
- 独立した上下唇へ `ParamMouthOpenY` のキーを追加。親の顔デフォーマを保ち、顔向きに追従させる。
- 口内は全開時の形を維持し、唇の遮蔽で開口を表現。口内だけを縮める既定の変形では半開きで下地の肌が露出するため、口の形ごとに開口0/0.5の形状を1からコピー。
- 中立・閉眼・開口、顔の左右上下、髪の揺れの画像を確認。
- 編集内容を `.psd2live` と `.cmo3` へ保存。`.can3` のモデル参照が壊れないよう、編集用CMO3とCAN3は元のbasenameを揃えて保持。

口内の既定形状を変更するため、書き出し時に口内の中立boundsが自動生成時の期待値と異なる警告が出ます。これは手動キーによる変更です。形状の一致警告と、公式Coreでのデータ不正・描画不正を区別して確認します。

## まとめ方と読み込み

実行用フォルダは次の構造です。ファイル名を変える場合はJSON内の参照も変更します。

```text
Revenant_Nizima/
  Revenant.model3.json
  Revenant.moc3
  Revenant.physics3.json
  Revenant.cdi3.json
  Revenant.4096/
    texture_00.png
    texture_01.png
  Revenant.*.motion3.json
  ico_Revenant.png
  README.txt
```

nizima LIVEのモデル一覧で「＋」を押し、`Revenant.model3.json` を選択します。フォルダ内のファイルはまとめて保持します。ZIP版は展開してから同じファイルを選びます。マーケットへの公開・出品はこの作業に含みません。

```bash
node tools/check-live2d-bundle.mjs /path/to/Revenant.model3.json
```

この検査は参照先の存在、JSON、PNG寸法、MOC3ヘッダーを確認します。MOC3内部の有効性や動作を判定する検査ではありません。公式Cubism Coreでの読込・パラメータ変形と、実アプリの表示を別に確認してください。

## 2026-10-16の変換記録

- 入力は4344×4344px・54層のneckwrap v8。原本を変更せず、分類用コピーの全層RGBA画素と座標の一致を確認。
- 54個のArtMesh、20パラメータ、4096×4096pxのテクスチャ2枚。実行用MOC3は1,015,936 bytes。
- モーションは待機・まばたき・うなずき・首振りの4種。まばたきとリップシンクのグループ、髪の物理設定を同梱。
- 最終MOC3を公式Native Core 06.00.0513で読込。整合検査成功、37,741頂点・41,139三角形、全20パラメータに実変形があり、各最小値・最大値で非有限座標なし。
- 公式Coreが返す頂点・UV・描画順・不透明度と、4件のクリッピング参照を使って最終MOC3を描画し、パーツとテクスチャの対応を確認。
- 実行用フォルダの参照9件、PNG寸法、MOC3ヘッダー、モーション4件とZIP整合を検査。原本PSDのSHA-256は作業前後で一致。
- 検証結果とアプリでの確認結果は本Issue/PRに記録する。

小さな顔向き・表情・呼吸の動作を想定しています。大きく横を向く、腕を高く上げる等の動作は追加の隠面素材とリギングが必要です。カメラ・iPhoneでの本人のトラッキング感度は利用環境で合わせてください。

## 笑顔とアクセサリーの揺れを追加した版

`Revenant_Smile/Revenant_Smile.model3.json` は、笑顔とアクセサリーの物理演算を追加した更新版です。旧版はそのまま保持し、モデル名も変えて登録します。編集用データは `Revenant_Smile_Editable`、確認画像と記録は `Revenant_Smile_Checks` に保存します。

### 笑顔

`ParamSmile`（0〜1、初期値0）で上下唇の口角、下まぶた、頬、眉を連動させています。上下唇では口開閉の両端、口内では口の形3点×口開閉3点の全組合せに笑顔キーを付け、会話中も笑顔を維持します。顔向きは既存の親デフォーマから引き継ぎます。

同梱する表情定義は [SoftSmile.exp3.json](../examples/nizima/SoftSmile.exp3.json) と [Smile.exp3.json](../examples/nizima/Smile.exp3.json) です。モデルフォルダの `expressions/` に置き、書き出した `model3.json` の `FileReferences.Expressions` に次を追加します。PSD2Liveで再書き出しした場合も、この参照を引き継いでください。

```json
"Expressions": [
  {"Name": "微笑み", "File": "expressions/SoftSmile.exp3.json"},
  {"Name": "笑顔", "File": "expressions/Smile.exp3.json"}
]
```

nizimaの「表情・モーション」から選びます。nizima LIVE 2.6.4の実画面ではファイル名の `SoftSmile`（微笑み）/ `Smile`（笑顔）として表示されます。表情を解除すると通常の顔へ戻ります。切り替える場合は前の表情を解除してください。目の開度はMultiplyで調整し、まばたきが残るようにしています。表情は `ParamMouthOpenY` を操作しません。

仕様は [nizimaの表情・モーション](https://docs.nizimalive.com/manual/expression-motion/) と [Live2Dのexp3仕様](https://github.com/Live2D/CubismSpecs/blob/master/FileFormats/exp3.json.md) を参照してください。

### アクセサリー

| 部品 | 動きと固定箇所 |
| --- | --- |
| ネックレスとペンダント | 同じWarpへまとめ、上側を固定して下側を遅らせる |
| 左右ピアス | 左右別々の揺れ。各側の表裏は同じWarpで同期 |
| 肩のリングとタグ | 上の留め部分を固定した小さな振り子 |
| 身頃のリング/チェーンとタグ | 左右で速度を少し変えた揺れ |
| 袖のタグ | 腕の親変形を引き継ぎ、タグに小さな揺れを追加 |
| 腰チェーン | 高さの違う両端を保ち、中央のたるみだけを動かす |

合計8個の出力パラメータを追加しています。ピアスは頭と体の入力を使い、胴体の装飾は主に体の入力へ接続します。腰チェーンを上辺固定のWarpへ入れると低い側の留め具が動くため、中央だけを選択したメッシュキーを物理演算へ接続しています。

[AccessoryDemo.motion3.json](../examples/nizima/AccessoryDemo.motion3.json) は6秒の確認用モーションです。`FileReferences.Motions.AccessoryDemo` へ参照を追加します。頭と体の4パラメータだけを動かし、アクセサリーの出力値は物理演算へ任せます。笑顔の値も上書きしません。

nizimaの一覧で区別できるよう、各モーションの実ファイル名を `Idle.motion3.json`、`Blink.motion3.json`、`Nod.motion3.json`、`Shake.motion3.json`、`AccessoryDemo.motion3.json` にします。先頭へ共通の `Revenant_Smile.` を付けると、実アプリでは最初のドットまでの同じ名前が5行に表示されました。ファイル名とモデルJSONの参照を一緒に更新します。

更新版は54 ArtMesh、29パラメータ、表情2種、モーション5種、物理演算10系統です。8系統のアクセサリーへ入力を1.5秒与えて戻し、60fps・6秒の数値検証で反応・振り戻し・減衰を確認しました。この条件で最大絶対値0.938、全出力の最終値0です。これは制作アプリ内の物理演算検証で、本人のカメラ/iPhoneによる調整とは区別します。最終MOC3の公式Core検証とnizimaでの実表示結果はIssue/PRへ記録します。

最終MOC3は公式Coreで整合検査に成功し、29パラメータすべてに実変形があり、全極値で非有限座標はありません。旧版との中立姿勢比較では全54メッシュの頂点数・index・UV・描画順・maskが一致し、頂点位置の最大差は4344pxキャンバス上で0.714pxです。表情2種と物理演算10系統の参照先パラメータも照合済みです。
