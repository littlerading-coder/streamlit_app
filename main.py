import streamlit as st
import pdfplumber
from openai import OpenAI
import json
import pandas as pd
import io

# ==========================================
# 1. 配置区域
# ==========================================
API_KEY = "sk-2057cfe4cf5c469daf501315fbd04dd6"  # <--- 【记得】替换你的 Key
BASE_URL = "https://api.deepseek.com"  # 或者 https://api.moonshot.cn/v1

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


# ==========================================
# 2. 核心函数
# ==========================================

def extract_text_from_pdf(file):
    """从 PDF 提取文本"""
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages[:10]:  # 仅演示前10页
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def generate_questions_json(text, q_type, count):
    """调用 AI 生成 JSON 格式的题目 (动态提示词版)"""

    # --- 关键修复：根据题目类型，动态调整给 AI 的指令和示例 ---
    if q_type == "多选题":
        example_answer = "A,C,D"  # 给一个多选的例子
        special_instruction = "【重要】这是一个多选题任务。每道题必须设置 2 个或 2 个以上的正确选项。答案用逗号分隔（如 'A,B'）。"
    elif q_type == "判断题":
        example_answer = "A"
        special_instruction = "【重要】这是一个判断题任务。'选项A'固定填'正确'，'选项B'固定填'错误'。其他选项留空。"
    else:  # 单选题
        example_answer = "B"
        special_instruction = "【重要】这是一个单选题任务。每道题只能有一个正确选项。"

    # --- 提示词构造 ---
    prompt = f"""
    你是一个专业的出题专家。请阅读标准内容，严格按照以下要求生成 {count} 道 {q_type}。

    {special_instruction}

    【输出格式要求】
    必须直接返回纯 JSON 格式数据列表，不要包含 Markdown 标记。

    返回示例：
    [
        {{
            "题干": "问题描述...",
            "选项A": "内容...", 
            "选项B": "内容...",
            "选项C": "内容...",
            "选项D": "内容...",
            "答案": "{example_answer}", 
            "解析": "根据标准第 x 章..."
        }}
    ]

    【标准内容片段】
    {text[:4000]}
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个只会输出 JSON 的出题助手。"},
                {"role": "user", "content": prompt},
            ],
            stream=False,
            temperature=0.3  # 稍微调高一点创造性，避免它死板地复制例子
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"调用 AI 出错: {e}")
        return None


# ==========================================
# 3. Streamlit 界面
# ==========================================

st.set_page_config(page_title="标准出题助手 (分列版)", page_icon="📊")
st.title("📊 AI 标准出题助手 (选项分列版)")

if 'generated_data' not in st.session_state:
    st.session_state.generated_data = None

with st.sidebar:
    st.header("⚙️ 设置")
    question_type = st.selectbox("题目类型", ["单选题", "多选题", "判断题"])
    question_count = st.slider("题目数量", 1, 10, 5)

uploaded_file = st.file_uploader("📂 上传 PDF 标准文件", type=["pdf"])

if uploaded_file:
    # 1. 解析文件
    if 'pdf_text' not in st.session_state:
        with st.spinner("正在读取 PDF..."):
            st.session_state.pdf_text = extract_text_from_pdf(uploaded_file)
            st.success(f"读取成功，共 {len(st.session_state.pdf_text)} 字")

    # 2. 生成按钮
    if st.button("🚀 生成并预览", type="primary"):
        with st.spinner("AI 正在思考并整理 Excel 格式..."):
            json_str = generate_questions_json(st.session_state.pdf_text, question_type, question_count)

            if json_str:
                clean_json_str = json_str.replace("```json", "").replace("```", "").strip()
                try:
                    data_list = json.loads(clean_json_str)
                    st.session_state.generated_data = data_list
                    st.success("生成成功！")
                except json.JSONDecodeError:
                    st.error("数据解析失败，请重试")

    # 3. 展示与下载
    if st.session_state.generated_data:
        st.divider()
        st.subheader("👀 预览结果")

        df = pd.DataFrame(st.session_state.generated_data)

        # 调整列顺序，让它在网页和 Excel 里看起来更顺眼
        # 这一步是为了防止 AI 返回的键顺序是乱的
        desired_columns = ["题干", "选项A", "选项B", "选项C", "选项D", "答案", "解析"]
        # 确保这些列都存在（防止 AI 漏掉某一列报错）
        for col in desired_columns:
            if col not in df.columns:
                df[col] = ""
        df = df[desired_columns]

        st.dataframe(df, use_container_width=True)

        # 导出逻辑
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='智能出题')
        output.seek(0)

        st.download_button(
            label="📥 下载 Excel 文件 (分列版)",
            data=output,
            file_name="AI试题_选项分列.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
