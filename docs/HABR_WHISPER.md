# Как мы в Delёz внедрили голосовой ввод на базе Whisper

Пишет об этом бэкенд-разработчик команды: **Васильев Данил**.

Цель этой статьи простая: показать, как мы в продукте **[Delёz](https://delez.tech)** внедряли **базовый голосовой ввод** в существующий FastAPI-бэкенд, какие проблемы встретили по пути и как их решили. Я специально расскажу не только «что такое Whisper», но и наш реальный инженерный путь: от первого рабочего варианта до боевого API.

---

## Цель и исходная точка

Когда мы стартовали задачу, в **[Delёz](https://delez.tech)** не было сценария «сказал голосом -> сохранил как запись дневника». Нам нужно было добавить:

1. Загрузку аудиофайла и получение текста.
2. Потоковый режим через WebSocket (чтобы пользователь видел промежуточный результат).
3. Сохранение результата в доменную сущность `Entry`.
4. Синхронизацию данных в Neo4j.

При этом не хотелось сразу городить отдельный ASR-микросервис. Поэтому мы выбрали внедрение Whisper прямо в API (у нас это помечено как «Вариант 2»).

---

## Почему именно Whisper и что важно про него знать

Мы выбрали **OpenAI Whisper** как зрелую open-source основу для ASR:

- Репозиторий: [openai/whisper](https://github.com/openai/whisper)
- Модель хорошо подходит для транскрипции мультиязычной речи.
- Быстро поднимается в Python и нормально интегрируется в существующий сервис.

Но есть важный практический момент: классический `openai-whisper` не дает «настоящий стриминг» из коробки, это скорее обработка файла/окон. Поэтому отдельно мы изучали подходы к real-time:

- Репозиторий: [ufal/whisper_streaming](https://github.com/ufal/whisper_streaming)

Он полезен как ориентир для low-latency подхода, но в нашем текущем проде напрямую не подключен как зависимость.

---

## Шаг 1. Вынесли работу с Whisper в инфраструктурный клиент

Первое решение: изолировать всю работу с моделью в отдельный класс `WhisperStreamingClient`, чтобы сервисный слой не знал деталей про temp-файлы, модель и executor.

```python
class WhisperStreamingClient:
    def __init__(self):
        self.model_name = settings.WHISPER_MODEL
        self.device = settings.WHISPER_DEVICE
        self.language = settings.WHISPER_LANGUAGE
        self._load_model()
```

### Проблема, в которую уперлись

`model.transcribe(...)` блокирует поток. Если вызвать его «как есть» внутри async-ручки FastAPI, можно подвесить event loop под нагрузкой.

### Как исправили

Запуск блокирующей части в `run_in_executor`:

```python
loop = asyncio.get_event_loop()
return await loop.run_in_executor(
    None,
    lambda: self._transcribe_file_sync(audio_file, language, kwargs),
)
```

Это была первая критичная стабилизация. После этого API перестал «тормозить» при распознавании больших файлов.

---

## Шаг 2. Сделали файловый endpoint и базовые защитные проверки

Дальше добавили `POST /v1/audio/transcribe` в `routes/audio.py`:

- проверка `Content-Type` (audio/video);
- ограничение размера файла (100 MB);
- вызов сервиса транскрипции;
- возврат `entry_id`, `text`, `language`, `duration`.

Пример нашей проверки размера:

```python
inner = file.file
inner.seek(0, 2)
file_size = inner.tell()
inner.seek(0)

if file_size > 100 * 1024 * 1024:
    return JSONResponse(status_code=400, content={"error": "File too large. Maximum size is 100MB."})
```

### Проблема

Без валидации входного файла легко получить перегруз по памяти и времени обработки.

### Решение

Жесткий лимит на уровне API + ранний отказ до запуска Whisper.

---

## Шаг 3. Связали транскрипцию с доменной моделью продукта

Чтобы это было не «демо распознавания», а часть продукта **[Delёz](https://delez.tech)**, мы сохраняем результат как `Entry`:

```python
entry = Entry(
    user_id=user_id,
    title=title or f"Audio transcription ({language})",
    description=text,
    event_date=event_date or date.today(),
    audio_source="upload",
    audio_duration=duration,
    transcription_model=f"whisper-{self.whisper_client.model_name}",
    transcription_language=language,
)
```

Потом делаем sync в Neo4j (`MERGE (e:Entry {id: ...})`), чтобы данные попадали в графовые сценарии.

### Проблема

Если sync в Neo4j падает, не хотелось ломать основной пользовательский сценарий.

### Решение

Ошибка синка логируется, но не откатывает уже успешно созданную запись в SQL.

---

## Шаг 4. Добавили потоковый режим через WebSocket

Следующая цель — дать пользователю «живой» опыт: отправляешь аудио-чанки, получаешь промежуточные куски текста.

В нашем `WebSocket /audio/stream`:

- токен берем из query или первого auth-сообщения;
- валидируем сессию через `AuthService.validate_session`;
- принимаем бинарные чанки;
- по мере распознавания шлем JSON с `text`, `is_final`.

```python
token = await _get_ws_token(websocket)
if not token:
    await websocket.close(code=1008, reason="Authentication required")
    return
```

### Проблема

Классический Whisper не стриминговый «по природе». Нельзя просто «кормить» его байтами и мгновенно получать финально стабильный текст.

### Решение (наш текущий компромисс)

Мы сделали **чанковый псевдостриминг**:

1. накапливаем байты до порога;
2. распознаем кусок;
3. отправляем partial-результат;
4. в конце отдаем финальный текст и сохраняем `Entry`.

Это не идеальный low-latency ASR, но практичный вариант для первого продакшен-релиза.

---

## Какие настройки оказались важными

Через `Settings` вынесли ключевые параметры:

- `WHISPER_MODEL` (по умолчанию `turbo`);
- `WHISPER_DEVICE` (`cpu`/`cuda`);
- `WHISPER_LANGUAGE` (auto или фиксированный язык).

Эти три переменные сильно влияют на задержку, качество и стоимость инфраструктуры.

---

## Что бы мы улучшали дальше

Наш текущий этап в **[Delёz](https://delez.tech)** — рабочий и стабильный baseline. Следующие шаги, которые логично развивать:

1. отдельный воркер/очередь под тяжелую ASR-нагрузку;
2. более продвинутый real-time пайплайн (ориентир — идеи из [ufal/whisper_streaming](https://github.com/ufal/whisper_streaming));
3. эксперименты с альтернативными бэкендами и ускорениями.

---

## Репозитории, на которые мы опирались

- OpenAI Whisper: [https://github.com/openai/whisper](https://github.com/openai/whisper)
- Whisper Streaming (исследовали как ориентир для real-time): [https://github.com/ufal/whisper_streaming](https://github.com/ufal/whisper_streaming)
- whisper.cpp (использовали как дополнительный reference для бета-тестового трека): [https://github.com/ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp)

---

## Итог

Мы внедрили голосовой ввод в **[Delёz](https://delez.tech)** без отдельного ASR-микросервиса: добавили файл+WebSocket сценарии, безопасные проверки входа, сохранение в доменную модель и синхронизацию в граф. Это дало пользователям рабочий голосовой путь уже на первом этапе, а нам — ясный фундамент для следующей итерации real-time качества.

Бета-тестирование голосового контура мы дополнительно сверяли с материалами и практиками из [whisper.cpp](https://github.com/ggml-org/whisper.cpp).
