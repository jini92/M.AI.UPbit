# M.AI.UPbit 콘텐츠 채널 전략

## 채널 분리

### 🇰🇷 한국어 채널
| 채널 | URL | 주기 | 타겟 |
|------|-----|------|------|
| Substack KR | (개설 예정) | 주간 | 국내 암호화폐 투자자 |
| 티스토리 | (개설 예정) | 주간 | 네이버 SEO |
| 네이버 카페 미러 | 업비트 공식 카페 | 격주 | 국내 커뮤니티 |

**콘텐츠 톤**: 친근하고 실용적, 투자 아이디어 공유형
**주요 키워드**: 퀀트투자, 업비트, 강환국, AI투자, 암호화폐 전략

### 🌐 영어 채널
| 채널 | URL | 주기 | 타겟 |
|------|-----|------|------|
| Medium | (개설 예정) | 주간 | 해외 개발자/퀀트 |
| Substack EN | (개설 예정) | 주간 | 해외 크립토 투자자 |
| GitHub Discussions | github.com/jini92/M.AI.UPbit | 월간 | OSS 기여자 |

**콘텐츠 톤**: 기술적, 데이터 중심, 오픈소스 기여 강조
**주요 키워드**: quant trading, upbit api, dual momentum, python crypto

## 콘텐츠 매핑

| 원본 데이터 | 한국어 | 영어 |
|------------|--------|------|
| 모멘텀 랭킹 | "이중 모멘텀 순위" | "Dual Momentum Rankings" |
| 매매 시그널 | "매매 시그널: 현금 유지" | "Signal: HOLD CASH" |
| 시즌 분석 | "시장 시즌: 강세장" | "Market Season: Bullish" |
| 팩터 분석 | "멀티팩터 분석" | "Multi-Factor Analysis" |

## 자동화 파이프라인

```
quant.py (데이터)
    ↓
generate_newsletter.py (한글 + 영어 초안 동시 생성)
    ↓
blog/drafts/
├── YYYY-MM-DD_Newsletter_KR.md  ← 티스토리/Substack KR
└── YYYY-MM-DD_Newsletter_EN.md  ← Medium/Substack EN
    ↓
n8n 자동 발행 (추후)
```
