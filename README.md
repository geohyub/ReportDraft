# 처리보고서 초안 (ProcessingReportDraft)

> 데이터 처리 보고서 자동 초안 작성

## 개요

GeoView 문서 관리 소프트웨어.
Python Flask 기반 웹 애플리케이션으로, 데이터 처리 보고서 자동 초안 작성 기능을 제공합니다. 테스트 코드 포함, Docker 지원.

## 기술 스택

- **언어**: Python
- **프레임워크**: Flask
- **UI**: Web UI
- **컨테이너**: Docker 지원
- **테스트**: 테스트 코드 포함

## 설치 및 실행

### 사전 요구사항

- Python 3.8 이상
- Python 패키지 (requirements.txt)

### 설치

```bash
pip install -r requirements.txt
```

### 실행 방법

```bash
run.bat
```

## 주요 의존성

- `click>=8.0`
- `python-docx>=1.1`
- `pyyaml>=6.0`
- `openpyxl>=3.1`
- `flask>=3.0`
- `waitress>=3.0`

## 프로젝트 구조

```
ProcessingReportDraft/
  main.py                         # 메인 엔트리포인트
  app.py                          # 애플리케이션 엔트리포인트
  requirements.txt                # Python 의존성
  Dockerfile                      # Docker 빌드 파일
  run.bat                         # Windows 실행 스크립트
  static/css/                     # 디렉토리
  static/js/                      # 디렉토리
  static/                         # 디렉토리
  templates/                      # 디렉토리
  tests/                          # 디렉토리
  core.py
  test.bat
```

## 라이선스

GeoView 내부 사용 전용
