# 코니처 — 팬트리 이전설치 홈페이지

실제 운영 사이트: **https://koniture-g-south.co.kr/** (가비아 웹호스팅)

SSL 인증서 만료일: **2027-03-17** — 만료 전 가비아에서 갱신 필요

이 저장소는 **백업 및 버전관리 용도**입니다. 사이트 배포처가 아닙니다.

---

## ⚠️ GitHub Pages 를 다시 켜지 마세요

이 저장소로 GitHub Pages 를 게시하면 **같은 내용의 사이트가 두 개**가 됩니다.
검색엔진은 중복 콘텐츠 중 하나만 선택하기 때문에, 실제 운영 사이트인
`koniture-g-south.co.kr` 이 검색 결과에서 밀려납니다.

실제로 2026년 8월에 이 문제가 발생했습니다.
`koniture-g-south.github.io` 만 네이버에 노출되고 `.co.kr` 은 노출되지 않았습니다.

### 완전히 꺼두는 방법

저장소를 프라이빗으로 두는 것만으로는 부족합니다.
퍼블릭으로 되돌리는 순간 Pages 설정이 살아날 수 있습니다.

```
GitHub 저장소 → Settings → Pages → Build and deployment → Source → None
```

여기서 `None` 으로 두는 것이 확실한 차단입니다.

### 이미 걸려 있는 안전장치

`index.html` 의 아래 두 줄이 "이 페이지의 정본은 .co.kr" 이라고 검색엔진에 알립니다.
**절대 지우거나 github.io 주소로 바꾸지 마세요.**

```html
<link rel="canonical" href="https://koniture-g-south.co.kr/">
<meta property="og:url" content="https://koniture-g-south.co.kr/">
```

---

## 사이트 수정 방법

1. 이 폴더에서 `index.html` 등을 수정
2. **가비아에 FTP 업로드** ← 이걸 해야 실제 사이트가 바뀝니다
   - My가비아 → 서비스 관리 → 호스팅 [관리툴] → 웹FTP
   - `index.html` 이 있는 최상위 폴더에 그대로 덮어쓰기
3. 백업 커밋 (선택)
   ```
   git add . && git commit -m "수정 내용" && git push
   ```

`git push` 만 하면 실제 사이트는 바뀌지 않습니다. 반드시 FTP 업로드가 필요합니다.

---

## 파일 구성

| 파일 | 설명 |
|---|---|
| `index.html` | 사이트 전체 (원페이지) |
| `robots.txt` | 검색로봇 수집 허용 설정 |
| `sitemap.xml` | 검색엔진 제출용 사이트맵 (이미지 12장 포함) |
| `1.jpg` ~ `12.jpg` | 시공 사례 사진 |
| `naverfe2d...html` | 네이버 사이트 소유확인 파일 — 지우지 마세요 |

## 남은 할 일

- [x] ~~HTTPS 적용~~ — 2026-08-30 완료 (가비아 SSL, www·non-www 모두 커버)
- [x] ~~`canonical` / `og:url` / `sitemap.xml` https 전환~~ — 완료
- [ ] **`.htaccess` 업로드** — http 접속을 https 로 넘기는 설정
- [ ] **네이버 서치어드바이저에 `https://` 주소를 새 사이트로 등록** (http 와 별개 취급)
- [ ] 네이버 스마트플레이스 등록
- [ ] 푸터에 사업자등록번호 · 사업장 주소 · 대표자명 추가
- [ ] 구글 서치콘솔 등록 (`index.html` 의 인증 태그 주석 해제)
