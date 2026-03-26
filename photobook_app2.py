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
PAPER_SIZES = {"2L版 (127x178mm)": (600, 840), "L版 (89x127mm)": (420, 600), "ハガキ (100x148mm)": (472, 700), "A4 (210x297mm)": (700, 990)}
FRAME_FILES = {"枠なし": None, "枠1 (シンプル)": "waku.png", "枠2 (装飾)": "waku2.png"}
PRESET_BG_COLORS = {"ホワイト ⚪": (255, 255, 255), "アイボリー 🍦": (245, 245, 240), "薄いグレー 🔘": (240, 240, 240), "セピア 📜": (224, 208, 176), "ブラック ⚫": (0, 0, 0), "🎨 カスタム": None}
PRESET_TEXT_COLORS = {"漆黒 ⚫": "#000000", "濃いグレー 🔘": "#333333", "ホワイト ⚪": "#FFFFFF", "ゴールド風 🟡": "#B8860B", "ダークブラウン 🪵": "#3D2B1F", "🎨 カスタム": None}
FONTS = {"ゴシック体 (現代的)": "msgothic.ttc", "明朝体 (厳か)": "msmincho.ttc"}

CARD_INNER_PAD = 36 
GAP = 12 

st.set_page_config(page_title="プロ・メモリアルエディタ", layout="wide")

# 💡 記憶の保管場所（Session State）の初期化
if "saved_text_img_url" not in st.session_state:
    st.session_state.saved_text_img_url = None
if "current_font_size" not in st.session_state:
    st.session_state.current_font_size = 45
if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = 0

# --- 2. 関数群 ---
def pil_to_data_url(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"

def build_base_paper(W, H, bg_rgb, frame_path):
    base = Image.new("RGBA", (W, H), (*bg_rgb, 255))
    if frame_path:
        full_path = os.path.join(os.path.dirname(__file__), frame_path)
        if os.path.exists(full_path):
            waku = Image.open(full_path).convert("RGBA").resize((W, H), Image.LANCZOS)
            base = Image.alpha_composite(base, waku)
    return base

def wrap_text(text: str, font, max_width: int):
    lines = []
    draw = ImageDraw.Draw(Image.new("RGBA", (1,1)))
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append(""); continue
        current_line = ""
        for char in list(paragraph):
            test_line = current_line + char
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] > max_width and current_line:
                lines.append(current_line); current_line = char
            else:
                current_line = test_line
        if current_line: lines.append(current_line)
    return "\n".join(lines)

def create_text_image(text, size, color, max_w, font_name, max_h=None):
    """テキスト画像を生成する共通関数（max_h指定で自動縮小）"""
    font_p = os.path.join(os.path.dirname(__file__), FONTS[font_name])
    current_size = size
    while current_size > 10:
        try: f_obj = ImageFont.truetype(font_p, current_size)
        except: f_obj = ImageFont.load_default()
        
        wrapped = wrap_text(text, f_obj, max_w - 60)
        draw = ImageDraw.Draw(Image.new("RGBA", (1,1)))
        bbox = draw.multiline_textbbox((0,0), wrapped, font=f_obj)
        tw, th = bbox[2]-bbox[0]+40, bbox[3]-bbox[1]+40
        
        # 高さ指定がある場合、収まるまでサイズを落とす
        if max_h and th > max_h:
            current_size -= 2; continue
        
        img = Image.new("RGBA", (int(tw), int(th)), (0,0,0,0))
        ImageDraw.Draw(img).multiline_text((tw//2, th//2), wrapped, font=f_obj, fill=color, anchor="mm", align="center")
        return pil_to_data_url(img), current_size
    return None, 10

# ========== 3. サイドバー ==========
with st.sidebar:
    st.header("📋 基本設定")
    selected_size = st.selectbox("出力サイズ", list(PAPER_SIZES.keys()))
    W, H = PAPER_SIZES[selected_size]
    selected_frame_key = st.radio("装飾枠の選択", list(FRAME_FILES.keys()))
    
    bg_preset = st.selectbox("背景色", list(PRESET_BG_COLORS.keys()))
    if bg_preset == "🎨 カスタム":
        bg_rgb = tuple(int(st.color_picker("背景色", "#FFFFFF").lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    else: bg_rgb = PRESET_BG_COLORS[bg_preset]

    st.header("📸 写真の設定")
    uploaded_file = st.file_uploader("写真をアップロード", type=["jpg","png","jpeg"])

    st.header("✍️ 文字の設定")
    user_text = st.text_area("本文", value="", height=100)
    
    # 💡 入力直後の「文字を反映」ボタン
    if st.button("📝 文字を反映・更新", type="primary", use_container_width=True):
        if user_text:
            url, final_s = create_text_image(user_text, st.session_state.current_font_size, "#000000", W, selected_font_name)
            st.session_state.saved_text_img_url = url
            st.session_state.refresh_key += 1
            st.rerun()

    selected_font_name = st.selectbox("フォント", list(FONTS.keys()))
    # スライダーが動いたらサイズを記憶
    new_size = st.slider("基本の文字サイズ", 10, 120, st.session_state.current_font_size)
    if new_size != st.session_state.current_font_size:
        st.session_state.current_font_size = new_size

    text_preset = st.selectbox("文字の色", list(PRESET_TEXT_COLORS.keys()))
    text_color = st.color_picker("カスタム文字色", "#000000") if text_preset == "🎨 カスタム" else PRESET_TEXT_COLORS[text_preset]

    st.divider()
    # 💡 自動調整ボタン
    if st.button("🤖 写真と文字枠を自動調整", use_container_width=True):
        if user_text and uploaded_file:
            # 写真サイズを仮定して残りの高さを計算
            p_img = ImageOps.contain(Image.open(uploaded_file).convert("RGBA"), (int(W*0.8), int(H*0.6)))
            safe_h = (H - (CARD_INNER_PAD + 20)) - (100 + p_img.height + GAP)
            url, final_s = create_text_image(user_text, st.session_state.current_font_size, text_color, W - 100, selected_font_name, max_h=safe_h)
            
            # 💡 結果を記憶（セッション）に保存
            st.session_state.saved_text_img_url = url
            st.session_state.current_font_size = final_s
            st.session_state.refresh_key += 1
            st.rerun()

    if st.button("🔄 全部リセット", use_container_width=True):
        st.session_state.saved_text_img_url = None
        st.session_state.refresh_key += 1
        st.rerun()

# ========== 4. メインエリア ==========
st.title("📱 メモリアルフォト＆メッセージ")

# 背景
base_paper = build_base_paper(int(W), int(H), bg_rgb, FRAME_FILES[selected_frame_key])
base_url = pil_to_data_url(base_paper)
objects_list = [{"type": "image", "src": base_url, "left": 0, "top": 0, "selectable": False, "evented": False}]

# 写真
if uploaded_file:
    p_img = ImageOps.contain(Image.open(uploaded_file).convert("RGBA"), (int(W*0.8), int(H*0.6)))
    objects_list.append({"type": "image", "src": pil_to_data_url(p_img), "left": (W - p_img.width)//2, "top": 100})

# 💡 文字（記憶にある場合はそれを使い、なければ新規作成）
if user_text:
    if st.session_state.saved_text_img_url is None:
        # 初回またはリセット後
        url, _ = create_text_image(user_text, st.session_state.current_font_size, text_color, W, selected_font_name)
        st.session_state.saved_text_img_url = url
    
    objects_list.append({
        "type": "image", 
        "src": st.session_state.saved_text_img_url, 
        "left": (W - 200)//2, # 中央付近
        "top": H - 250        # 下部付近
    })

# キャンバス表示
canvas_result = st_canvas(
    fill_color="rgba(0,0,0,0)",
    background_color="#eeeeee",
    initial_drawing={"objects": objects_list},
    height=int(H), width=int(W),
    drawing_mode="transform",
    key=f"canvas_{st.session_state.refresh_key}_{selected_size}_{selected_frame_key}",
)

# 保存
st.divider()
if st.button("✨ デザインを確定する", use_container_width=True, type="primary"):
    if canvas_result.image_data is not None:
        final_layer = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
        complete_page = Image.new("RGB", (int(W), int(H)), (255, 255, 255))
        complete_page.paste(base_paper.convert("RGB"))
        complete_page.paste(final_layer, mask=final_layer.split()[3])
        
        st.success("✅ 保存の準備ができました")
        c1, c2 = st.columns(2)
        buf_j = io.BytesIO(); complete_page.save(buf_j, format="JPEG", quality=95)
        c1.download_button("📥 JPEG保存", buf_j.getvalue(), "memorial.jpg", "image/jpeg", use_container_width=True)
        buf_p = io.BytesIO(); complete_page.save(buf_p, format="PDF", resolution=100.0)
        c2.download_button("📥 PDF保存", buf_p.getvalue(), "memorial.pdf", "application/pdf", use_container_width=True)