# Level Calculation

## 기본 공식

```
Level = floor(sqrt(uses * 10))
EXP = uses * 10
Next Level EXP = (level + 1)² * 10
EXP to Next = Next Level EXP - EXP
```

## 레벨 테이블

| Level | 필요 사용횟수 | 누적 EXP | 등급 |
|-------|--------------|----------|------|
| 1 | 1 | 10 | 초보 |
| 5 | 3 | 30 | 입문 |
| 10 | 10 | 100 | 숙련 |
| 15 | 23 | 230 | 능숙 |
| 20 | 40 | 400 | 전문가 |
| 25 | 63 | 630 | 마스터 |
| 30 | 90 | 900 | 그랜드마스터 |
| 50 | 250 | 2500 | 레전드 |

## 레벨 칭호

| 레벨 범위 | 칭호 | 설명 |
|-----------|------|------|
| 1-4 | 초보 | 스킬 탐색 중 |
| 5-9 | 입문 | 기본 사용법 습득 |
| 10-14 | 숙련 | 익숙하게 사용 |
| 15-19 | 능숙 | 활용도 높음 |
| 20-24 | 전문가 | 주력 스킬 |
| 25-29 | 마스터 | 완전 숙달 |
| 30-49 | 그랜드마스터 | 최고 수준 |
| 50+ | 레전드 | 전설적 사용자 |

## 진행률 표시

```
Lv.12 ████████░░ 80% → Lv.13
```

진행률 = (현재 EXP - 현재 레벨 EXP) / (다음 레벨 EXP - 현재 레벨 EXP) * 100

## JavaScript 구현

```javascript
function calculateLevel(uses) {
  const exp = uses * 10;
  const level = Math.floor(Math.sqrt(exp));
  const currentLevelExp = level * level * 10;
  const nextLevelExp = (level + 1) * (level + 1) * 10;
  const progress = (exp - currentLevelExp) / (nextLevelExp - currentLevelExp);

  return {
    level,
    exp,
    currentLevelExp,
    nextLevelExp,
    expToNext: nextLevelExp - exp,
    usesToNext: Math.ceil((nextLevelExp - exp) / 10),
    progress: Math.round(progress * 100)
  };
}

function getTitle(level) {
  if (level >= 50) return '레전드';
  if (level >= 30) return '그랜드마스터';
  if (level >= 25) return '마스터';
  if (level >= 20) return '전문가';
  if (level >= 15) return '능숙';
  if (level >= 10) return '숙련';
  if (level >= 5) return '입문';
  return '초보';
}
```

## 레벨업 이벤트

레벨업 시 표시:
```
🎉 레벨 업!
━━━━━━━━━━━━━━━━
/commit: 숙련 Lv.9 → 숙련 Lv.10
칭호 변경 없음
다음 레벨까지: 11회 사용
━━━━━━━━━━━━━━━━
```

칭호 변경 시:
```
🎊 칭호 획득!
━━━━━━━━━━━━━━━━
/commit: Lv.14 → Lv.15
🏅 숙련 → 능숙
━━━━━━━━━━━━━━━━
```
