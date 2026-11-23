# evals

`claude plugin eval` 케이스. 가상 인물(홍길동) 데이터와 함정 공고로 글쓰기 단계를 시험한다.
설명, 실행 방법, 한계는 [docs/grading.md](../docs/grading.md)에 있다.

```bash
claude plugin eval . --scaffold --allow-tools Write Edit --runs 1 --no-publish
```

- `_fixtures/seed.sh`: 평가 실행의 임시 HOME 에 예제 데이터(`~/.job-apply`, `~/materials`, `~/postings`)를 깐다
- `_fixtures/posting_*.md`: 함정 공고, 양식 공고
- `_fixtures/bad_final.md`: 채점기 점검용 나쁜 예
