# 테스트 작성 규칙 및 알려진 이슈

## editor.text 직접 할당: 언제 허용하고 언제 금지하는가

`editor.text = "..."` 는 `CodeEditor` reactive 프로퍼티를 직접 변경하며,
**`TextArea` 위젯의 렌더링된 내용은 바꾸지 않는다.**

### 허용: 단위 테스트에서 reactive 레이어 검증

`test_code_editor.py`, `test_main_view.py`, `test_app.py`에서는 직접 할당이 적합하다.

- 목적: `CodeEditor`의 reactive 로직 (`watch_text`, `update_title`,
  `has_unsaved_pane()` 등)을 테스트하는 것이지, 실제 타이핑 흐름이 아님
- `TextArea` 시각 내용이 스크린샷에 캡처되지 않으므로 경쟁 조건이 노출되지 않음

```python
# OK: reactive 레이어 동작 확인
editor.text = "modified\n"
await pilot.pause()
assert editor.title.endswith("*")
```

### 허용: 스냅샷에서 TextArea 내용이 아닌 상태 변경 시각화

탭 제목의 `*` 같이 TextArea 내용이 아닌 UI 요소를 찍을 때는 직접 할당이 더 안정적이다.
`pilot.press()` 는 커서 위치 등 시각 노이즈를 유발할 수 있다.

```python
# test_snapshot_unsaved_marker 에서 사용 - 탭 제목 * 검증
editor.text = "modified content\n"
await pilot.pause()
# snapshot: tab title shows *, TextArea still shows original content
```

### 금지: 스냅샷에서 "파일이 수정됨"이라는 앱 로직에 의존할 때

`app.action_quit()`, `ctrl+w` 처럼 `has_unsaved_pane()` 결과에 따라 동작이
달라지는 흐름에서 직접 할당을 쓰면 **flaky** 해진다.

**원인**: `pilot.pause()` 이후 Textual 이벤트 루프가 `TextArea.Changed`를 처리하면
`editor.text` 가 TextArea의 현재 내용(원본)으로 덮어 쓰일 수 있다. 그 결과
`has_unsaved_pane()` 가 False를 반환해 모달이 열리지 않고 앱이 즉시 종료된다.

```python
# BAD: 경쟁 조건 발생 가능
editor.text = "modified\n"
await pilot.pause()
app.action_quit()   # has_unsaved_pane() 이 False 를 반환할 수도 있음
```

```python
# GOOD: pilot.press() 로 TextArea.Changed 흐름 전체를 거침
editor.action_focus()
await pilot.pause()
await pilot.press("x")
await pilot.pause()
app.action_quit()   # has_unsaved_pane() 가 확실히 True
```

---

## 알려진 Flaky 스냅샷 테스트

두 스냅샷 테스트가 `@pytest.mark.xfail(strict=False)` 로 마크되어 있다.

### 근본 원인

`app.py` 의 `action_open_code_editor` 가 `editor.call_later(editor.action_focus)` 로
포커스를 비동기 예약한다. 이 지연된 포커스 이벤트가 `snap_compare` 의 `run_before`
콜백과 경쟁하여 비결정적 렌더링 상태를 만든다.

```python
# app.py - 원인 코드
editor.call_later(editor.action_focus)   # 비동기 예약 → 타이밍 불확정
```

**수정 방향** (아직 미구현): `call_later` 대신 `await editor.action_focus()` 로
변경하거나, `on_ready` 전체를 async/await 체인으로 처리해야 한다.

### 영향받는 테스트

| 테스트 | 이유 |
|--------|------|
| `test_snapshot_unsaved_change_modal` | `pilot.press("x")` + `ctrl+w` 흐름에서 포커스 경쟁 |
| `test_snapshot_unsaved_quit_modal`   | `pilot.press("x")` + `action_quit()` 흐름에서 포커스 경쟁 |

`xfail(strict=False)` 이므로 통과 시 `xpassed`, 실패 시 `xfailed` 로 보고되며
전체 테스트 결과에는 영향을 주지 않는다.

---

## 스냅샷 재생성 방법

스냅샷은 **반드시 전체 테스트 스위트와 함께** 갱신해야 한다.
`tests/test_snapshots.py` 만 단독으로 `--snapshot-update` 하면
비스냅샷 테스트가 남긴 전역 상태가 반영되지 않아 비교 시 불일치가 발생한다.

```bash
# 올바른 방법: 전체 테스트로 갱신
uv run pytest tests/ --snapshot-update

# 틀린 방법: 스냅샷만 단독 갱신 (이후 전체 실행 시 일부 실패 가능)
uv run pytest tests/test_snapshots.py --snapshot-update
```
