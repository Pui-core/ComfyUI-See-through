# 男性立ち絵：原画と体下地の分割

`workflows/seethrough-revenant-original.json` と `workflows/seethrough-revenant-body.json` を順番に実行します。既存のSee-throughノードだけを使用します。画像は同梱していません。

## 入力

ComfyUIのinputフォルダへ以下の名前で画像を置くか、Load Imageでアップロードします。

- `revenant_original.png`: 花・装飾が付いた最初の原画。
- `revenant_body.png`: 装飾を除去した体の下地。

現在の入力は両方1086×1448です。別寸法へ変更する場合はEmpty Imageの幅・高さも合わせてください。透明部分を白で合成してから分割モデルへ送ります。入力のMASKは透明領域が白なのでInvertMaskで反転しています。

## 実行

1. originalを開き、Run。入力プレビューと分割プレビューを確認します。
2. SavePSDの「Download PSD」を押して原画のPSDを保存します。
3. bodyを開いて同様に実行し、体下地のPSDを保存します。
4. PSD編集ソフトで原画PSDを基準に、下地PSDから必要な肌・衣服のパーツだけを移します。原画と下地には生成による差があるので、位置・輪郭・重なりを手動で調整します。
5. 花・蔓が衣服に融合していた場合は、原画から手動マスクで切り出します。不要な下地側の髪・顔は採用しません。

SavePSDは実行時に各パーツPNGと位置情報付きlayers.jsonをComfyUI/outputへ保存します。PSDはボタンから組み立てます。PNG単体は全キャンバスではなくクロップされているため、原位置を保つにはPSDまたはlayers.jsonの座標を使ってください。出力プレフィックスはrevenant_originalとrevenant_bodyです。

## 設定

- 両seed: 246813579 / fixed
- レイヤー推論: 768 / 30steps
- 深度: -1（レイヤー解像度に従う）
- group_offload: true（メモリ節約、処理速度とのトレードオフ）
- cache_tag_embeds: true
- auto_download: true（未導入モデルは初回にダウンロード）
- 左右分割: true
- use_lama: false（追加LaMa依存を避けOpenCVで補完）

GPUメモリ不足なら推論解像度を512へ下げます。解像度を上げても構造の誤認識は修正されません。出力キャンバスはモデル内部の正方形化等の処理を受けるため、1086×1448を保証せずPSD/layers.jsonを確認してください。2本の解像度設定はそろえます。

## 限界と確認状況

生成ベースの分割候補であり、原画の画素・幾何形状の完全保持、花や蔓の個別認識、自動位置合わせ、2つのPSDの自動合成を保証しません。手動の境界修正・隠れた部分の補完が残ります。PSD作成だけでLive2Dのリギングまで完了するものではありません。

JSON構文、ソケット型、リンク両端、循環の有無、実際の導入済みノード定義を確認。GPU推論・GUIでのPSDダウンロードは未実施です。
