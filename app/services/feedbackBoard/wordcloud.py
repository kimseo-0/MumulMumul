# app/services/feedback_board/wordcloud.py

from typing import Dict, List
from pathlib import Path

from wordcloud import WordCloud


def generate_wordclouds_per_category(
    wc_text_by_category: Dict[str, List[str]],
    output_dir: str,
) -> Dict[str, str]:
    """
    카테고리별로 워드클라우드 PNG를 생성하고
    {category: file_path} 를 반환한다.
    """
    output = {}
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for category, texts in wc_text_by_category.items():
        if not texts:
            continue

        full_text = "\n".join(texts)

        wc = WordCloud(
            width=800,
            height=400,
            background_color="white",
            font_path="C:/Windows/Fonts/malgun.ttf",  # 한글이면 폰트 지정 필요
        ).generate(full_text)

        fname = out_dir / f"wordcloud_{category}.png"
        wc.to_file(str(fname))
        output[category] = str(fname)

    return output
