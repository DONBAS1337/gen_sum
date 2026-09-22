# Generative Summer — Windows compatibility fix

Неофициальный фикс для Steam Workshop-мода **«Генеративное лето»**
для Everlasting Summer.

Workshop ID мода:

```text
3800447567
```

## Что исправлено

### 1. Импорт модулей `gs_backend` и `gs_core`

`gs_runtime.py` запускается отдельным процессом и в некоторых случаях не мог
найти соседние Python-модули, если текущая рабочая папка отличалась от папки
мода.

Исправление: каталог самого `gs_runtime.py` явно добавляется в `sys.path`
перед импортом `gs_backend` и `gs_core`.

### 2. Обрывы генерации на встроенном Python 2.7

Everlasting Summer использует старый Ren'Py Python 2.7.18.

На длинных streaming-запросах `/responses` соединение регулярно обрывалось:

```text
SSL read timeout
IncompleteRead
Соединение прервалось до завершения сцены
```

Исправление: текстовая генерация вынесена в отдельный системный Python 3.

При этом:

- сама игра продолжает работать на штатном Python 2.7;
- Ren'Py и `pygame_sdl2` остаются без изменений;
- сохранения и генерация фонов продолжают обрабатываться игровым runtime.

### 3. Сетевой транспорт `/responses`

Даже системный Python 3 через стандартный `urllib/http.client` мог
нестабильно держать длинный SSE-поток.

Исправление: только запросы генерации текста `/responses` выполняются через
системный `curl.exe`:

```text
curl.exe --http1.1 --no-buffer
```

OAuth, список моделей и остальные запросы остаются на штатной логике мода.

### 4. Python 2 → Python 3 bridge

Дополнительно исправлены две проблемы bridge:

- не используется `Popen(..., env=...)`, который ломался в Ren'Py Python 2
  с ошибкой `environment can only contain strings`;
- результат Python 3 передаётся через временный JSON-файл вместо большого
  stdout-pipe, чтобы избежать возможной блокировки на длинной генерации.

## Зависимости

### Обязательно

- Windows 10 или Windows 11;
- Everlasting Summer;
- установленный **системный Python 3**;
- системный `curl.exe`.

Фикс проверен с:

```text
Python 3.14.3
```

Именно Python 3.14 не обязателен — нужен современный Python 3.

На современных Windows `curl.exe` обычно уже установлен.

### Проверить Python 3

В PowerShell:

```powershell
python --version
```

Если команда `python` не работает, это не обязательно проблема.

Фикс умеет автоматически искать Python в стандартных местах, включая
Python Install Manager:

```text
%LOCALAPPDATA%\Microsoft\WindowsApps\PythonSoftwareFoundation.PythonManager_*\python.exe
```

Также проверяются:

```text
%LOCALAPPDATA%\Programs\Python\Python3*\python.exe
%ProgramFiles%\Python3*\python.exe
```

При необходимости путь можно задать вручную через переменную окружения:

```powershell
[Environment]::SetEnvironmentVariable(
    "GS_PYTHON3",
    "C:\Path\To\Python\python.exe",
    "User"
)
```

После этого полностью перезапустите Steam.

### Проверить curl

```powershell
curl.exe --version
```

## Установка

Папка Workshop-мода обычно находится здесь:

```text
<SteamLibrary>\steamapps\workshop\content\331470\3800447567\mods\generative_summer
```

Например:

```text
D:\SteamLibrary\steamapps\workshop\content\331470\3800447567\mods\generative_summer
```

Перед установкой полностью закройте Everlasting Summer.

### Вариант 1 — вручную

Скопируйте из папки `ready_replace` в папку мода:

```text
gs_backend.py
gs_runtime.py
gs_text_worker.py
```

с заменой существующих файлов.

После этого удалите старые compiled-файлы, если они существуют:

```text
gs_backend.pyo
gs_runtime.pyo
```

Это важно: Ren'Py может загрузить старый `.pyo` вместо нового `.py`.

`gs_core.py` менять не нужно.

Фикс работает с полным оригинальным каталогом ресурсов, включая все варианты
спрайтов `close` и `far`.

### Вариант 2 — install.ps1

Запустите PowerShell в папке фикса:

```powershell
.\install.ps1 -ModDir "D:\SteamLibrary\steamapps\workshop\content\331470\3800447567\mods\generative_summer"
```

Installer:

- создаст резервную копию заменяемых файлов;
- установит исправленные `.py`;
- удалит старые `gs_backend.pyo` и `gs_runtime.pyo`;
- проверит наличие `curl.exe`.

## Как работает фикс

```text
Everlasting Summer / Ren'Py
        |
        | Python 2.7
        v
gs_runtime.py
        |
        v
gs_backend.py
        |
        | запускает системный Python 3
        v
gs_text_worker.py
        |
        | curl.exe / HTTP/1.1
        v
ChatGPT /responses
```

Python 3 используется только для текстовой генерации.

## Проверка после установки

В папке мода можно проверить, видит ли встроенный Python игры системный
Python 3.

Пример:

```powershell
$py = "D:\SteamLibrary\steamapps\common\Everlasting Summer\lib\windows-i686\python.exe"

& $py -c "import gs_backend; print(gs_backend._external_python3())"
```

В ответ должен появиться путь к Python 3, например:

```text
C:\Users\...\PythonSoftwareFoundation.PythonManager_...\python.exe
```

После этого можно запускать обычную генерацию истории через интерфейс мода.

## Важно

Steam Workshop может перезаписать изменённые файлы после обновления мода или
проверки его файлов.

Сохраните копию фикса отдельно и при необходимости установите его повторно.
