# 原画と体下地のPSD合成ワークフロー

SeeThroughのSavePSDが保存した `*_layers.json` と各レイヤーPNGを読み戻し、原画側の指定レイヤーだけを体下地側に置き換え、SavePSDで新しいPSDを作ります。PSDバイナリを直接読む機能ではありません。PNG＋JSONを残してあれば分割モデルの再実行は不要です。

## 導入

`extras/ComfyUI-Revenant-Merge` フォルダをComfyUI/custom_nodesへコピーし、ComfyUIを再起動してください。既存のSeeThrough本体は変更しません。必要依存はComfyUIに通常含まれるnumpy/Pillow/torchです。

`workflows/seethrough-revenant-merge.json` を読み込みます。

## 操作

1. 原画・体下地の分割ワークフローをそれぞれ実行済みであることを確認します。
2. ComfyUI/outputにある `revenant_original_日時_ID_layers.json` と `revenant_body_日時_ID_layers.json` を01/02へ指定します。outputからの相対ファイル名、または実行中のComfyUIから見える絶対パスです。Windows版ではWindowsパスを指定し、WSLの `/mnt/c/...` は入力しません。
3. 初期設定は `neck` と `topwear` の置換です。検出されない名前はエラーに両入力の候補名を表示します。まず一覧だけ確認したければreplace_partsを空にして実行してください。初期名が実際のモデル出力と一致する保証はありません。
4. replace_partsに置換対象を1行ずつ入力します。髪・顔・装飾など、指定していない原画側パーツは保持されます。同名パーツが両入力に存在する場合だけ置換します。衣服に花が焼き込まれている場合は、花が自動で独立するわけではありません。
5. 必要ならoffset_x/offset_yを調整します。正のxは右、正のyは下。対象は選択した下地パーツだけです。部位別の調整はMergeノードを直列に追加し、前段のpartsを次段のoriginalへ、同じ下地をunderlayへ渡して1パーツずつ設定します。
6. 不要な原画パーツを消す場合のみremove_partsへ名前を入力します。置換対象と同時指定はできません。
7. Runで原画と合成プレビューを比較します。SavePSDにPNGとlayers.jsonが保存されるので、結果がよければ **Download PSD** を押してください。

プレビューの灰色背景は確認用で、レイヤーPNGに焼き込まれません。変更していないパーツのRGBAは保持します。置換パーツには原画側のdepth_medianを継承し、別推論間の深度値をそのまま混ぜません。同じ深度のパーツの順序は原画manifestの順に従います。

キャンバスが異なる場合は停止します。自動リサイズ、自動位置合わせ、輪郭修復、部分マスク合成、隠れた部分の生成はしません。XYで直せない変形・縮尺差はPSD編集ソフトで修正してください。

各PNGはクロップ画像で、座標はJSONへ保持されます。PSDを使用すると元位置で重なります。深度PNGは読み戻していないため **Download Depth PSDではなくDownload PSD** を使います。元のJSON/PNGは上書きせず、revenant_mergedの新しい出力を作ります。

## 検証

`python3 -m unittest discover -s tests -p test_saved_merge.py -v`

選択置換、非対象RGBA保持、入力非破壊、原画深度順保持、XY、キャンバス不一致、未知名・全削除拒否、manifest読込、ディレクトリ外参照拒否、重複名拒否、透過重ね合わせをCPUで確認。ワークフローJSON接続を検証。ComfyUIのGUI実行と実画像PSDの完成品質は未確認です。
