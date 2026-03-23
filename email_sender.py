import os
import resend

resend.api_key = os.environ.get(
    "RESEND_API_KEY", "re_CrZ19kyT_GJXTbTxu4Bxk6NqQTwuZdSRP"
)

FROM_EMAIL = "순위리포트 <onboarding@resend.dev>"


def build_report_html(shop: dict, weekly_avg: dict, history: list) -> str:
    weeks_html = ""
    for week in [1, 2, 3, 4]:
        label = ["4주 전", "3주 전", "2주 전", "이번 주"][week - 1]
        avg = weekly_avg.get(week)
        if avg is not None:
            rank_text = f"<span style='font-size:36px;font-weight:800;color:#03c75a'>{avg}<span style='font-size:16px'>위</span></span>"
            # 변동 표시
            if week > 1 and weekly_avg.get(week - 1) is not None:
                diff = weekly_avg[week - 1] - avg
                if diff > 0:
                    rank_text += f"<br><span style='color:#03c75a;font-size:13px'>▲ {diff}단계 상승</span>"
                elif diff < 0:
                    rank_text += f"<br><span style='color:#ff4d4f;font-size:13px'>▼ {-diff}단계 하락</span>"
                else:
                    rank_text += "<br><span style='color:#999;font-size:13px'>— 변동 없음</span>"
        else:
            rank_text = "<span style='color:#ddd;font-size:14px'>데이터 없음</span>"

        weeks_html += f"""
        <td style="width:25%;text-align:center;padding:16px 8px;background:#f8f9fa;border-radius:12px">
            <div style="font-size:13px;color:#999;margin-bottom:8px">{label}</div>
            {rank_text}
        </td>
        """

    # 최근 7일 기록
    recent = history[-7:] if history else []
    rows_html = ""
    for r in reversed(recent):
        rank_display = f"{r['rank']}위" if r.get("rank") else "-"
        rows_html += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0">{r['checked_at'][:10]}</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;color:#03c75a;font-weight:700">{rank_display}</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0">{r.get('save_count') or '-'}</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0">{r.get('blog_review') or '-'}</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0">{r.get('visitor_review') or '-'}</td>
        </tr>
        """

    place_display = shop.get("place_name") or shop.get("place_id", "")

    return f"""
    <div style="max-width:520px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#333">
        <div style="background:#fff;border-radius:16px;padding:32px;margin-bottom:16px;box-shadow:0 2px 12px rgba(0,0,0,0.06)">
            <h1 style="font-size:20px;margin-bottom:4px">{place_display}</h1>
            <span style="display:inline-block;background:#e8f8ee;color:#03c75a;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:600;margin-bottom:20px">
                {shop['keyword']}
            </span>
            <p style="color:#888;font-size:14px;margin-bottom:16px">최근 30일 주차별 평균 순위</p>
            <table style="width:100%;border-spacing:8px;border-collapse:separate">
                <tr>{weeks_html}</tr>
            </table>
        </div>
        <div style="background:#fff;border-radius:16px;padding:32px;box-shadow:0 2px 12px rgba(0,0,0,0.06)">
            <h2 style="font-size:16px;margin-bottom:12px">최근 기록</h2>
            <table style="width:100%;border-collapse:collapse;font-size:13px">
                <thead>
                    <tr style="color:#999;font-size:12px">
                        <th style="text-align:left;padding:8px;border-bottom:2px solid #eee">날짜</th>
                        <th style="text-align:left;padding:8px;border-bottom:2px solid #eee">순위</th>
                        <th style="text-align:left;padding:8px;border-bottom:2px solid #eee">저장</th>
                        <th style="text-align:left;padding:8px;border-bottom:2px solid #eee">블로그</th>
                        <th style="text-align:left;padding:8px;border-bottom:2px solid #eee">방문자</th>
                    </tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>
            {'' if rows_html else '<p style="text-align:center;color:#bbb;padding:20px">아직 수집된 데이터가 없습니다</p>'}
        </div>
        <p style="text-align:center;color:#bbb;font-size:12px;margin-top:16px">네이버 플레이스 순위 리포트</p>
    </div>
    """


async def send_report(email: str, shop: dict, weekly_avg: dict, history: list):
    place_display = shop.get("place_name") or shop.get("place_id", "")
    html = build_report_html(shop, weekly_avg, history)

    resend.Emails.send({
        "from": FROM_EMAIL,
        "to": [email],
        "subject": f"[순위리포트] {place_display} - {shop['keyword']} 주간 리포트",
        "html": html,
    })
