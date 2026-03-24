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

# --- 定数 ---
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
# プリセット色 + カスタム選択肢
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

st.set_page_config(page_title="プロ・メモリアルエディタ", layout="wide")

def get_script_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()

def pil_to_data_url(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"

def hex_to_rgb(hex_str: str) -> tuple:
    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def build_base_paper(W, H, bg_rgb, frame_path):
    base = Image.new("RGBA", (W, H), (*bg_rgb, 255))
    if frame_path:
        full_path = os.path.join(get_script_dir(), frame_path)
        if os.path.exists(full_path):
            try:
                waku = Image.open(full_path).convert("RGBA").resize((W, H), Image.LANCZOS)
                base = Image.alpha_composite(base, waku)
            except Exception as e:
                st.warning(f"枠読み込みエラー: {e}")
        else:
            st.warning(f"枠ファイルが見つかりません: {full_path}")
    return base

def wrap_text(text: str, font, max_width: int, draw: ImageDraw.Draw) -> str:
    """
    テキストを max_width に収まるよう折り返す。
    ユーザーが入力した改行（\n）は保持する。
    """
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        words = list(paragraph)  # 日本語は1文字ずつ
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

def prepare_text_image(text: str, size: int, color: str, max_w: int, f_path: str) -> Image.Image:
    """
    テキストを max_w 幅で折り返してPIL画像に変換する。
    color は "#RRGGBB" 形式。
    """
    font_full_path = os.path.join(get_script_dir(), f_path)
    try:
        font = ImageFont.truetype(font_full_path, size) if os.path.exists(font_full_path) else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    # 折り返し幅 = キャンバス幅の85%（余白確保）
    wrap_width = int(max_w * 0.85)

    # 折り返し計算用のダミー画像
    dummy = Image.new("RGBA", (max_w * 2, 100))
    dd = ImageDraw.Draw(dummy)

    wrapped_text = wrap_text(text, font, wrap_width, dd)

    # 折り返し後のテキストサイズを計測
    bbox = dd.multiline_textbbox((0, 0), wrapped_text, font=font, align="center")
    tw = int(bbox[2] - bbox[0] + 60)
    th = int(bbox[3] - bbox[1] + 60)

    txt_img = Image.new("RGBA", (max(tw, 100), max(th, 50)), (0, 0, 0, 0))
    ImageDraw.Draw(txt_img).multiline_text(
        (tw // 2, th // 2),
        wrapped_text,
        font=font,
        fill=color,
        anchor="mm",
        align="center"
    )
    return txt_img

# ========== サイドバー ==========
with st.sidebar:
    st.header("📋 基本設定")
    selected_size = st.selectbox("出力サイズ", list(PAPER_SIZES.keys()))
    W, H = PAPER_SIZES[selected_size]
    selected_frame_key = st.radio("装飾枠の選択", list(FRAME_FILES.keys()))
    frame_path = FRAME_FILES[selected_frame_key]

    # --- 背景色 ---
    bg_preset = st.selectbox("背景色", list(PRESET_BG_COLORS.keys()))
    if bg_preset == "🎨 カスタム":
        bg_hex = st.color_picker("背景色を選択", "#FFFFFF", key="bg_custom")
        bg_rgb = hex_to_rgb(bg_hex)
    else:
        bg_rgb = PRESET_BG_COLORS[bg_preset]

    st.header("📸 写真の設定")
    uploaded_file = st.file_uploader("写真をアップロード", type=["jpg","png","jpeg"])

    st.header("✍️ 文字の設定")
    user_text = st.text_area("本文", value="", placeholder="メッセージを入力...\n（長い文章は自動で折り返されます）")
    selected_font_name = st.selectbox("フォント", list(FONTS.keys()))
    text_size = st.slider("文字のサイズ", 10, 120, 45)

    # --- 文字色 ---
    text_preset = st.selectbox("文字の色", list(PRESET_TEXT_COLORS.keys()))
    if text_preset == "🎨 カスタム":
        text_color = st.color_picker("文字色を選択", "#000000", key="text_custom")
    else:
        text_color = PRESET_TEXT_COLORS[text_preset]

    st.divider()
    if st.button("🔄 画面を強制リセット"):
        st.rerun()

# ========== メイン ==========
st.title("📱 メモリアルフォト＆メッセージ")

base_paper = build_base_paper(int(W), int(H), bg_rgb, frame_path)
base_paper_url = pil_to_data_url(base_paper)

# 背景をオブジェクトの最背面に（選択・移動不可）
objects_list = [
    {
        "type": "image",
        "src": base_paper_url,
        "left": 0, "top": 0,
        "scaleX": 1, "scaleY": 1,
        "selectable": False,
        "evented": False,
        "lockMovementX": True,
        "lockMovementY": True,
        "lockRotation": True,
        "lockScalingX": True,
        "lockScalingY": True,
        "hasControls": False,
        "hasBorders": False,
    }
]

if uploaded_file:
    p_img = Image.open(uploaded_file).convert("RGBA")
    p_img = ImageOps.contain(p_img, (int(W*0.8), int(H*0.6)))
    objects_list.append({
        "type": "image",
        "src": pil_to_data_url(p_img),
        "left": int((W - p_img.width) // 2),
        "top": 120,
        "scaleX": 1, "scaleY": 1,
    })

if user_text:
    t_img = prepare_text_image(
        user_text, text_size, text_color, W, FONTS[selected_font_name]
    )
    objects_list.append({
        "type": "image",
        "src": pil_to_data_url(t_img),
        "left": int((W - t_img.width) // 2),
        "top": int(H * 0.75),
        "scaleX": 1, "scaleY": 1,
    })

bg_key = "_".join(map(str, bg_rgb))
# カスタム色対応のため text_color の文字列もキーに含める
c_key = (
    f"cv_{bg_key}_{selected_frame_key}_{selected_size}"
    f"_{'y' if uploaded_file else 'n'}_{len(user_text)}_{text_size}_{text_color.replace('#','')}"
)

canvas_result = st_canvas(
    fill_color="rgba(255,255,255,0)",
    stroke_width=0,
    background_image=None,
    background_color="rgba(0,0,0,0)",
    initial_drawing={"objects": objects_list},
    height=int(H),
    width=int(W),
    drawing_mode="transform",
    key=c_key,
)

# ========== 確定と保存 ==========
st.divider()
if st.button("✨ デザインを確定する", use_container_width=True, type="primary"):
    if canvas_result.image_data is not None:
        final_layer = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
        complete_page = Image.alpha_composite(base_paper, final_layer)

        st.success("✅ 準備完了！保存ボタンを押してください。")
        c1, c2 = st.columns(2)

        buf_j = io.BytesIO()
        complete_page.convert("RGB").save(buf_j, format="JPEG", quality=95)
        c1.download_button("📥 通常保存 (JPEG)", buf_j.getvalue(), "memorial.jpg", "image/jpeg", use_container_width=True)

        buf_p = io.BytesIO()
        complete_page.convert("RGB").save(buf_p, format="PDF", resolution=100.0)
        c2.download_button("📥 高画質保存 (PDF)", buf_p.getvalue(), "memorial.pdf", "application/pdf", use_container_width=True)
    else:
        st.warning("キャンバスにコンテンツがありません。")