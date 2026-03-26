import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image, ImageDraw, ImageFont, ImageOps
import base64
import os
import io
import numpy as np

# --- Streamlit用パッチ (クラウド環境での画像表示エラーを回避) ---
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
    """画像をBase64形式の文字列に変換する"""
    buf = io.BytesIO()
    img.convert("RGBA").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

def prepare_text_image_fitting(text, size, color, target_w, target_h, f_path):
    """
    💡 文字が指定の枠（target_h）に収まるまでフォントサイズを自動調整する
    """
    f_path_full = os.path.join(os.getcwd(), f_path)
    low = 10
    high = size
    best_size = low
    
    test_img = Image.new("RGBA", (int(target_w), 500))
    test_draw = ImageDraw.Draw(test_img)

    while low <= high:
        mid = (low + high) // 2
        try: test_font = ImageFont.truetype(f_path_full, mid)
        except: test_font = ImageFont.load_default()
        
        wrapped_text = ""
        current_line = ""
        for char in list(text):
            test_line = current_line + char
            if test_draw.textbbox((0, 0), test_line, font=test_font)[2] > target_w * 0.95:
                wrapped_text += current_line + "\n"
                current_line = char
            else:
                current_line = test_line
        wrapped_text += current_line
        
        bbox = test_draw.multiline_textbbox((0, 0), wrapped_text, font=test_font, align="center")
        th = int(bbox[3] - bbox[1] + 40)
        
        if th <= target_h:
            best_size = mid
            low = mid + 1
        else:
            high = mid - 1
            
    try: final_font = ImageFont.truetype(f_path_full, best_size)
    except: final_font = ImageFont.load_default()
    
    wrapped_text = ""
    current_line = ""
    for char in list(text):
        test_line = current_line + char
        if test_draw.textbbox((0, 0), test_line, font=final_font)[2] > target_w * 0.95:
            wrapped_text += current_line + "\n"
            current_line = char
        else:
            current_line = test_line
    wrapped_text += current_line

    bbox = test_draw.multiline_textbbox((0, 0), wrapped_text, font=final_font, align="center")
    tw, th = int(bbox[2] - bbox[0] + 60), int(bbox[3] - bbox[1] + 60)
    
    txt_img = Image.new("RGBA", (max(tw, 100), max(th, 50)), (0, 0, 0, 0))
    ImageDraw.Draw(txt_img).multiline_text((tw//2, th//2), wrapped_text, font=final_font, fill=color, anchor="mm", align="center")
    return txt_img, best_size

def make_bg(design_name):
    path = DESIGNS.get(design_name)
    if path and os.path.exists(path):
        bg = Image.open(path).convert("RGBA")
    else:
        # デフォルトベージュ
        bg = Image.new("RGBA", (CARD_W, 400), (245, 240, 225, 255))
    
    card_h = int(CARD_W * bg.height / bg.width)
    canvas_h = card_h + PADDING * 2

    # ★ 修正: キャンバス全体（パディング含む）を1枚の画像として合成
    canvas = Image.new("RGBA", (CANVAS_W, canvas_h), (240, 235, 230, 255))
    canvas.paste(bg.resize((CARD_W, card_h)), (PADDING, PADDING))
    return canvas, card_h, canvas_h

# ==========================================
# 🤖 自動レイアウト
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
        pw, ph = (aw - GAP * (cols - 1)) // cols, (ph_area_h - GAP * (rows - 1)) // rows
        for i in range(n): rects.append((x0 + (i % cols) * (pw + GAP), y0 + (i // cols) * (ph + GAP), pw, ph))

    for info, (rx, ry, rw, rh) in zip(photo_infos, rects):
        scale = min(rw / info["w"], rh / info["h"])
        objects.append({
            "type": "image", "src": info["src"],
            "left": int(rx + (rw - info["w"]*scale)//2), "top": int(ry + (rh - info["h"]*scale)//2),
            "scaleX": scale, "scaleY": scale, "originX": "left", "originY": "top"
        })
    
    if all_text:
        ty = y0 + ph_area_h + GAP
        color = text_defs[0].get("fill", "#333333") if text_defs else "#333333"
        txt_img, best_size = prepare_text_image_fitting(all_text, 32, color, aw, text_zone_h, FONT_FILE)
        objects.append({
            "type": "image", "src": pil_to_b64(txt_img),
            "left": x0 + (aw - txt_img.width)//2, "top": ty + (text_zone_h - txt_img.height)//2,
            "originX": "left", "originY": "top"
        })
    return objects

# ==========================================
# UI
# ==========================================
st.set_page_config(page_title="プロ・メモリアルカード", layout="wide")
st.title("🕯️ プロ・メモリアルカード (AI自動レイアウト版)")

if "canvas_objects" not in st.session_state:
    st.session_state.update({"canvas_objects": [], "processed": {}, "canvas_key": 0, "design": list(DESIGNS.keys())[0], "text_defs": [], "mode": "手動"})

with st.sidebar:
    st.header("🖼️ 背景デザイン")
    new_design = st.selectbox("デザイン切替", list(DESIGNS.keys()), index=list(DESIGNS.keys()).index(st.session_state.design))
    if new_design != st.session_state.design:
        st.session_state.design = new_design
        st.session_state.canvas_key += 1
        st.rerun()

    st.divider()
    st.header("📸 写真を追加")
    uploaded = st.file_uploader("写真を選択", accept_multiple_files=True)
    if uploaded:
        new_fs = [f for f in uploaded if f.name not in st.session_state.processed]
        if new_fs and st.button(f"🖼️ {len(new_fs)}枚を反映"):
            for f in new_fs:
                c = resize_pil(Image.open(f).convert("RGBA"), PHOTO_MAX_PX)
                st.session_state.processed[f.name] = {"src": pil_to_b64(c), "w": c.width, "h": c.height}
            st.session_state.canvas_key += 1; st.rerun()

    st.divider()
    st.header("✍️ 文字を追加")
    msg = st.text_area("本文", "想い出をありがとう。")
    t_color = st.color_picker("文字色", "#333333")
    if st.button("📝 文字を登録"):
        st.session_state.text_defs.append({"type": "i-text", "text": msg, "fill": t_color})
        st.session_state.canvas_key += 1; st.rerun()

    st.divider()
    st.session_state.mode = st.radio("配置モード", ["手動", "AIで自動レイアウト"])
    if st.session_state.mode == "AIで自動レイアウト" and st.button("🤖 自動レイアウトを適用", type="primary"):
        _, card_h_tmp, _ = make_bg(st.session_state.design)
        st.session_state.canvas_objects = auto_layout(list(st.session_state.processed.values()), st.session_state.text_defs, CARD_W, card_h_tmp)
        st.session_state.canvas_key += 1; st.rerun()

    if st.button("🔄 リセット"):
        for k in ["canvas_objects", "processed", "text_defs"]: st.session_state[k] = [] if k != "processed" else {}
        st.session_state.canvas_key += 1; st.rerun()

# --- メインエリア ---
bg_pil, card_h, canvas_h = make_bg(st.session_state.design)

# ★ 修正ポイント: background_image(PIL)ではなく background_url(Base64文字列)を使用
bg_b64_url = pil_to_b64(bg_pil)

st.subheader("2. 写真・文字を配置してください")
canvas_result = st_canvas(
    fill_color="rgba(0,0,0,0)",
    background_url=bg_b64_url,          # ← ここを変更（PIL→Base64 URL）
    # background_image=bg_pil,          # ← この行を削除（PIL渡しは廃止）
    initial_drawing={"objects": st.session_state.canvas_objects},
    height=canvas_h, width=CANVAS_W, drawing_mode="transform",
    key=f"cv_{st.session_state.design}_{st.session_state.canvas_key}"
)

# 保存
if st.button("✅ 完成画像を確定する", type="primary", use_container_width=True):
    if canvas_result.image_data is not None:
        rgba = Image.fromarray(canvas_result.image_data.astype(np.uint8), "RGBA")
        merged = Image.alpha_composite(bg_pil.convert("RGBA"), rgba)
        final = merged.crop((PADDING, PADDING, PADDING + CARD_W, PADDING + card_h)).convert("RGB")
        st.image(final, caption="完成プレビュー", use_container_width=True)
        buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
        st.download_button("📥 ダウンロード", buf.getvalue(), "card.jpg", "image/jpeg")