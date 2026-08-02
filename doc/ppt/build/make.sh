#!/bin/bash
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
V22_SRC="$1"          # v2.2 解壓目錄
OUT="$2"              # 輸出 pptx
cd "$HERE"
node build.js "_base.pptx" >/dev/null
rm -rf _pkg && mkdir _pkg && (cd _pkg && unzip -oq ../_base.pptx)
# 照搬 v2.2 的 slide7–16（XML + rels + 其引用的圖），不做任何修改
for i in $(seq 7 16); do
  cp "$V22_SRC/ppt/slides/slide$i.xml"            _pkg/ppt/slides/slide$i.xml
  cp "$V22_SRC/ppt/slides/_rels/slide$i.xml.rels" _pkg/ppt/slides/_rels/slide$i.xml.rels
done
cp "$V22_SRC/ppt/media/image3.png" "$V22_SRC/ppt/media/image4.png" "$V22_SRC/ppt/media/image5.png" _pkg/ppt/media/
rm -f "$OUT"
(cd _pkg && zip -q -X -0 "$OUT" '[Content_Types].xml' && zip -q -X -r "$OUT" . -x '[Content_Types].xml' -x '.*')
echo "✓ $OUT"
