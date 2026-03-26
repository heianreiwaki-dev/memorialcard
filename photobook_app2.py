import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
import os
import base64

# ==========================================
# 🚨 エラー回避パッチ
# ==========================================
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

# --- 1. 定数・設定 ---
PAPER_SIZES = {
    "2L版 (127x178mm)": (600, 840),
    "L版 (89x127mm)": (420, 600),
    "ハガキ (100x148mm)": (472, 700),
    "A4 (210x297mm)": (700, 990)
}
FRAME_FILES = {
    "枠なし": None,
    "枠1 (シンプル)": "waku.png",
    "枠2 (装飾)": "waku2.png"
}
PRESET_BG_COLORS = {
    "ホワイト ⚪": (255, 255, 255),
    "アイボリー 🍦": (245, 245, 240),
    "薄いグレー 🔘": (240, 240, 240),
    "セピア 📜": (224, 208, 176),
    "ブラック ⚫": (0, 0, 0),
    "🎨 カスタム": None,
}
PRESET_TEXT_COLORS = {
    "漆黒 ⚫": "#000000",
    "濃いグレー 🔘": "#333333",
    "ホワイト ⚪": "#FFFFFF",
    "ゴールド風 🟡": "#B8860B",
    "ダークブラウン 🪵": "#3D2B1F",
    "🎨 カスタム": None,
}
FONTS = {
    "ゴシック体 (現代的)": "msgothic.ttc",
    "明朝体 (厳か)": "msmincho.ttc"
}

CARD_INNER_PAD = 36 
GAP = 12 

st.set_page_config(page_title="プロ・メモリアルエディタ", layout="wide")

# 状態管理の初期化
if "auto_layout_run" not in st.session_state:
    st.session_state.auto_layout_run = False
if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = 0

# --- 2. 関数群 ---
def pil_to_data_url(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"

def build_base_paper(W, H, bg_rgb, frame_path):
    base = Image.new("RGBA", (W, H), (*bg_rgb, 255))
    if frame_path:
        # Streamlit Cloudでのパス解決を確実に
        full_path = os.path.join(os.path.dirname(__file__), frame_path)
        if os.path.exists(full_path):
            waku = Image.open(full_path).convert("RGBA").resize((W, H), Image.LANCZOS)
            base = Image.alpha_composite(base, waku)
    return base

def wrap_text(text: str, font, max_width: int, draw: ImageDraw.Draw) -> str:
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        words = list(paragraph) 
        current_line = ""
        for char in words:
            test_line = current_line + char
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] > max_width and current_line:
                lines.append(current_line)
                current_line = char
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)
    return "\n".join(lines)

def prepare_text_image_fitting(text: str, initial_size: int, color: str, safe_w: int, safe_h: int, f_path: str) -> tuple:
    font_full_path = os.path.join(os.path.dirname(__file__), f_path)
    font_size = initial_size
    min_size = 10
    
    while font_size >= min_size:
        try:
            font = ImageFont.truetype(font_full_path, font_size) if os.path.exists(font_full_path) else ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        dd_dummy = ImageDraw.Draw(Image.new("RGBA", (safe_w * 2, 100)))
        wrapped_text = wrap_text(text, font, safe_w, dd_dummy)
        bbox = dd_dummy.multiline_textbbox((0, 0), wrapped_text, font=font, align="center")
        tw, th = int(bbox[2] - bbox[0] + 40), int(bbox[3] - bbox[1] + 40)
        
        if tw <= safe_w and th <= safe_h:
            txt_img = Image.new("RGBA", (max(tw, 100), max(th, 50)), (0, 0, 0, 0))
            ImageDraw.Draw(txt_img).multiline_text((tw // 2, th // 2), wrapped_text, font=font, fill=color, anchor="mm", align="center")
            return txt_img, font_size
        font_size -= 2
    
    return Image.new("RGBA", (100, 50), (0,0,0,0)), min_size

# ========== 3. サイドバー ==========
with st.sidebar:
    st.header("📋 基本設定")
    selected_size = st.selectbox("出力サイズ", list(PAPER_SIZES.keys()))
    W, H = PAPER_SIZES[selected_size]
    
    # 枠や色が変わったらリフレッシュキーを増やす
    selected_frame_key = st.radio("装飾枠の選択", list(FRAME_FILES.keys()))
    frame_path = FRAME_FILES[selected_frame_key]

    bg_preset = st.selectbox("背景色", list(PRESET_BG_COLORS.keys()))
    if bg_preset == "🎨 カスタム":
        bg_rgb = tuple(int(st.color_picker("背景色", "#FFFFFF").lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    else:
        bg_rgb = PRESET_BG_COLORS[bg_preset]

    st.header("📸 写真の設定")
    uploaded_file = st.file_uploader("写真をアップロード", type=["jpg","png","jpeg"])

    st.header("✍️ 文字の設定")
    user_text = st.text_area("本文", value="")
    selected_font_name = st.selectbox("フォント", list(FONTS.keys()))
    text_size = st.slider("文字のサイズ", 10, 120, 45)
    
    text_preset = st.selectbox("文字の色", list(PRESET_TEXT_COLORS.keys()))
    text_color = st.color_picker("カスタム文字色", "#000000") if text_preset == "🎨 カスタム" else PRESET_TEXT_COLORS[text_preset]

    st.divider()
    if st.button("🤖 写真と文字枠を自動調整", type="primary", use_container_width=True):
        st.session_state.auto_layout_run = True
        st.session_state.refresh_key += 1 # 強制リフレッシュ

    if st.button("🔄 全部リセット", use_container_width=True):
        st.session_state.auto_layout_run = False
        st.session_state.refresh_key += 1
        st.rerun()

# ========== 4. メインエリア ==========
st.title("📱 メモリアルフォト＆メッセージ")

# 背景台紙の生成
base_paper = build_base_paper(int(W), int(H), bg_rgb, frame_path)
base_url = pil_to_data_url(base_paper)

# 💡 背景をオブジェクトとして配置（最背面）
objects_list = [{
    "type": "image", "src": base_url, "left": 0, "top": 0,
    "selectable": False, "evented": False, "lockMovementX": True, "lockMovementY": True,
    "lockRotation": True, "lockScalingX": True, "lockScalingY": True
}]

# 写真の配置
if uploaded_file:
    p_img = ImageOps.contain(Image.open(uploaded_file).convert("RGBA"), (int(W*0.8), int(H*0.6)))
    p_url = pil_to_data_url(p_img)
    p_top = 100
    objects_list.append({
        "type": "image", "src": p_url, "left": (W - p_img.width)//2, "top": p_top, "scaleX": 1, "scaleY": 1
    })

# 文字の配置
if user_text:
    margin = CARD_INNER_PAD + 20
    safe_w = W - margin * 2
    
    if st.session_state.auto_layout_run and uploaded_file:
        txt_area_top = 100 + p_img.height + GAP
        txt_area_h = (H - margin) - txt_area_top
        t_img, f_size = prepare_text_image_fitting(user_text, text_size, text_color, safe_w, txt_area_h, FONTS[selected_font_name])
        t_top = txt_area_top + (txt_area_h - t_img.height)//2
        st.sidebar.info(f"🤖 自動調整完了: {f_size}px")
    else:
        # 手動モード時のデフォルト作成（前回の wrap_text を利用）
        font_p = os.path.join(os.path.dirname(__file__), FONTS[selected_font_name])
        f_obj = ImageFont.truetype(font_p, text_size) if os.path.exists(font_p) else ImageFont.load_default()
        wrapped = wrap_text(user_text, f_obj, safe_w, ImageDraw.Draw(Image.new("RGBA", (1,1))))
        bbox = ImageDraw.Draw(Image.new("RGBA", (1,1))).multiline_textbbox((0,0), wrapped, font=f_obj)
        tw, th = bbox[2]-bbox[0]+40, bbox[3]-bbox[1]+40
        t_img = Image.new("RGBA", (int(tw), int(th)), (0,0,0,0))
        ImageDraw.Draw(t_img).multiline_text((tw//2, th//2), wrapped, font=f_obj, fill=text_color, anchor="mm", align="center")
        t_top = int(H * 0.7)

    objects_list.append({
        "type": "image", "src": pil_to_data_url(t_img), "left": (W - t_img.width)//2, "top": t_top
    })

# 💡 強力なリフレッシュキーの生成
c_key = f"canvas_{st.session_state.refresh_key}_{selected_size}_{selected_frame_key}_{bg_preset}"

# 自動調整フラグの戻し
if st.session_state.auto_layout_run:
    st.session_state.auto_layout_run = False

canvas_result = st_canvas(
    fill_color="rgba(0,0,0,0)",
    background_color="#eeeeee", # キャンバスの外側の色
    initial_drawing={"objects": objects_list},
    height=int(H), width=int(W),
    drawing_mode="transform",
    key=c_key,
)

# 保存処理
st.divider()
if st.button("✨ デザインを確定する", use_container_width=True, type="primary"):
    if canvas_result.image_data is not None:
        final_layer = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
        # 背景と合成
        complete_page = Image.new("RGB", (int(W), int(H)), (255, 255, 255))
        complete_page.paste(base_paper.convert("RGB"))
        complete_page.paste(final_layer, mask=final_layer.split()[3])
        
        st.success("✅ 保存の準備ができました")
        c1, c2 = st.columns(2)
        buf_j = io.BytesIO()
        complete_page.save(buf_j, format="JPEG", quality=95)
        c1.download_button("📥 JPEG保存", buf_j.getvalue(), "memorial.jpg", "image/jpeg", use_container_width=True)
        buf_p = io.BytesIO()
        complete_page.save(buf_p, format="PDF", resolution=100.0)
        c2.download_button("📥 PDF保存", buf_p.getvalue(), "memorial.pdf", "application/pdf", use_container_width=True)