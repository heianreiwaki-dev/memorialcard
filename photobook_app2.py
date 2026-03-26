import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image, ImageDraw, ImageFont, ImageOps
import base64
import os
import io
import numpy as np

# --- Streamlit用パッチ (表示エラー回避) ---
import streamlit.elements.image as st_image
import streamlit.elements.lib.image_utils as image_utils
if not hasattr(st_image, "image_to_url"):
    st_image.image_to_url = image_utils.image_to_url
class FakeLayoutConfig:
    def __init__(self, width):
        self.width = width
        self.use_container_width = False
original_image_to_url = st_image.image_to_url
def patched_image_to_url(image, width_or_config, *args, **kwargs):
    if isinstance(width_or_config, (int, float)):
        width_or_config = FakeLayoutConfig(int(width_or_config))
    return original_image_to_url(image, width_or_config, *args, **kwargs)
st_image.image_to_url = patched_image_to_url
image_utils.image_to_url = patched_image_to_url

# ==========================================
# 定数・設定
# ==========================================
CARD_W = 560
PADDING = 80
CANVAS_W = CARD_W + PADDING * 2
PHOTO_MAX_PX = 350
CARD_INNER_PAD = 36 
GAP = 12
FONT_FILE = "msgothic.ttc" 

CARDS_DIR = "cards"
os.makedirs(CARDS_DIR, exist_ok=True)

def load_designs():
    exts = (".jpg", ".jpeg", ".png")
    files = sorted([f for f in os.listdir(CARDS_DIR) if f.lower().endswith(exts)])
    designs = {os.path.splitext(f)[0]: os.path.join(CARDS_DIR, f) for f in files}
    designs["（標準・ベージュ）"] = None
    return designs

DESIGNS = load_designs()

# ==========================================
# ユーティリティ
# ==========================================
def resize_pil(img, max_px):
    w, h = img.size
    r = max_px / max(w, h)
    return img.resize((int(w*r), int(h*r)), Image.LANCZOS)

def pil_to_b64(img):
    buf = io.BytesIO()
    img.convert("RGBA").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

def make_bg(design_name):
    path = DESIGNS.get(design_name)
    if path and os.path.exists(path):
        bg = Image.open(path).convert("RGBA")
    else:
        # デフォルト背景（ベージュ系）を生成
        bg = Image.new("RGBA", (CARD_W, 400), (245, 240, 225, 255))
    
    card_h = int(CARD_W * bg.height / bg.width)
    canvas_h = card_h + PADDING * 2
    canvas = Image.new("RGBA", (CANVAS_W, canvas_h), (210, 205, 200, 255))
    canvas.paste(bg.resize((CARD_W, card_h)), (PADDING, PADDING))
    return canvas, card_h, canvas_h

# ==========================================
# 🤖 自動レイアウトロジック
# ==========================================
def auto_layout(photo_infos, text_defs, card_w, card_h):
    n = len(photo_infos)
    objects = []
    margin = CARD_INNER_PAD + 15
    x0, y0 = PADDING + margin, PADDING + margin
    aw, ah = card_w - margin * 2, card_h - margin * 2

    all_text = "\n".join([t.get("text", "") for t in text_defs])
    if all_text:
        text_zone_h = max(int(ah * 0.3), int(ah * min(0.5, len(all_text) / 200)))
        ph_area_h = max(ah - text_zone_h - GAP, 40)
    else:
        text_zone_h = 0
        ph_area_h = ah

    rects = []
    if n == 1: rects = [(x0, y0, aw, ph_area_h)]
    elif n >= 2:
        cols = 2 if n <= 4 else 3
        rows = (n + cols - 1) // cols
        pw = (aw - GAP * (cols - 1)) // cols
        ph = (ph_area_h - GAP * (rows - 1)) // rows
        for i in range(n): rects.append((x0 + (i % cols) * (pw + GAP), y0 + (i // cols) * (ph + GAP), pw, ph))

    for info, (rx, ry, rw, rh) in zip(photo_infos, rects):
        scale = min(rw / info["w"], rh / info["h"])
        objects.append({
            "type": "image", "src": info["src"],
            "left": int(rx + (rw - info["w"]*scale)//2),
            "top": int(ry + (rh - info["h"]*scale)//2),
            "scaleX": scale, "scaleY": scale, "originX": "left", "originY": "top"
        })
    
    if all_text:
        # テキストオブジェクト（位置のみ調整）
        ty = y0 + ph_area_h + GAP
        for t in text_defs:
            obj = dict(t)
            obj.update({"left": x0 + aw//2, "top": ty, "originX": "center"})
            objects.append(obj)
            ty += t.get("fontSize", 28) + 10
            
    return objects

# ==========================================
# メイン UI
# ==========================================
st.set_page_config(page_title="プロ・メモリアルカード", layout="wide")
st.title("🕯️ プロ・メモリアルカード (AI自動レイアウト版)")

if "canvas_objects" not in st.session_state:
    st.session_state.update({
        "canvas_objects": [], "processed": {}, "canvas_key": 0,
        "design": list(DESIGNS.keys())[0], "text_defs": [], "mode": "手動"
    })

with st.sidebar:
    st.header("🖼️ 背景デザイン")
    design_names = list(DESIGNS.keys())
    new_design = st.selectbox("デザイン切替", design_names, index=design_names.index(st.session_state.design))
    if new_design != st.session_state.design:
        st.session_state.design = new_design
        st.session_state.canvas_key += 1
        st.rerun()

    st.divider()
    st.header("📸 写真を追加")
    uploaded_files = st.file_uploader("写真を選択", accept_multiple_files=True)
    if uploaded_files:
        new_files = [f for f in uploaded_files if f.name not in st.session_state.processed]
        if new_files and st.button(f"🖼️ {len(new_files)}枚を反映"):
            for f in new_files:
                pil = Image.open(f).convert("RGBA")
                c = resize_pil(pil, PHOTO_MAX_PX)
                info = {"src": pil_to_b64(c), "w": c.width, "h": c.height}
                st.session_state.processed[f.name] = info
                if st.session_state.mode == "手動":
                    st.session_state.canvas_objects.append({"type": "image", "src": info["src"], "left": 100, "top": 100, "scaleX": 1.0, "scaleY": 1.0})
            st.session_state.canvas_key += 1
            st.rerun()

    st.divider()
    st.header("✍️ 文字を追加")
    msg = st.text_area("本文", "想い出をありがとう。")
    t_color = st.color_picker("文字色", "#333333")
    if st.button("📝 文字を登録"):
        text_obj = {"type": "i-text", "text": msg, "fill": t_color, "fontSize": 28, "fontFamily": "ゴシック体", "left": 100, "top": 400}
        if st.session_state.mode == "AIで自動レイアウト":
            st.session_state.text_defs.append(text_obj)
        else:
            st.session_state.canvas_objects.append(text_obj)
        st.session_state.canvas_key += 1
        st.rerun()

    st.divider()
    st.header("🤖 レイアウト設定")
    st.session_state.mode = st.radio("配置モード", ["手動", "AIで自動レイアウト"])
    if st.session_state.mode == "AIで自動レイアウト":
        if st.button("🤖 自動レイアウトを適用", type="primary"):
            p_infos = list(st.session_state.processed.values())
            _, card_h_tmp, _ = make_bg(st.session_state.design)
            st.session_state.canvas_objects = auto_layout(p_infos, st.session_state.text_defs, CARD_W, card_h_tmp)
            st.session_state.canvas_key += 1
            st.rerun()

    if st.button("🔄 リセット"):
        for k in ["canvas_objects", "processed", "text_defs"]: st.session_state[k] = [] if k != "processed" else {}
        st.session_state.canvas_key += 1
        st.rerun()

# --- メインエリア ---
bg_pil, card_h, canvas_h = make_bg(st.session_state.design)
# 💡 背景をBase64に変換して渡すことで表示を確実にする
bg_data_url = pil_to_b64(bg_pil)

st.subheader("2. 写真・文字を配置してください")
c_key = f"cv_{st.session_state.design}_{st.session_state.canvas_key}"

canvas_result = st_canvas(
    fill_color="rgba(0,0,0,0)",
    background_image=bg_pil,
    initial_drawing={"objects": st.session_state.canvas_objects},
    height=canvas_h, width=CANVAS_W,
    drawing_mode="transform",
    key=c_key,
)

# 確定・保存
if st.button("✅ 完成画像を確定する", type="primary", use_container_width=True):
    if canvas_result.image_data is not None:
        rgba = Image.fromarray(canvas_result.image_data.astype(np.uint8), "RGBA")
        merged = Image.alpha_composite(bg_pil.convert("RGBA"), rgba)
        final = merged.crop((PADDING, PADDING, PADDING + CARD_W, PADDING + card_h)).convert("RGB")
        st.image(final, caption="完成プレビュー", use_container_width=True)
        buf = io.BytesIO()
        final.save(buf, format="JPEG", quality=95)
        st.download_button("📥 完成品をダウンロード (JPEG)", buf.getvalue(), "memorial_card.jpg", "image/jpeg")