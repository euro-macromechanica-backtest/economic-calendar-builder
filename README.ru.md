# Euro Macromechanica (EMM) Backtest — Economic Calendar Builder 
*economic calendar builder (code-only)*
 
> 🧭 Этот репозиторий является частью экосистемы **Euro Macromechanica (EMM) Backtest**.

---

## ‼️ Читайте главный  [results/`README.ru.md`](https://github.com/euro-macromechanica-backtest/results/blob/main/README.ru.md)` экосистемы **Euro Macromechanica Backtest (EMM)!

---

## 📚 Связанная экосистема

- **Результаты бэктеста, доказательство наличия стратегии, политика качества данных (headline/stress), integrity-материалы** — *[results](https://github.com/euro-macromechanica-backtest/results)*  
- **Подготовленные агрегаты/данные для воспроизводимости** — *[data-hub](https://github.com/euro-macromechanica-backtest/data-hub)*
- **Анализатор и нормализатор минутных данных** - *[minute-data-analyzer](https://github.com/euro-macromechanica-backtest/minute-data-analyzer)*

---

## 🧭 Назначение

**economic calendar builder** — собирает ключевые макро-релизы (центробанки/статведомства).

Подробная иснтрукция и ньюансы в [`AUDIT.ru.md`](https://github.com/euro-macromechanica-backtest/results/blob/main/AUDIT.ru.md).
Также см. в [`data-hub/economic-calendars/README.ru.md`](https://github.com/euro-macromechanica-backtest/data-hub/tree/main/economic_calendars/README.md).

> Код намеренно лаконичный: отдельные детали могут быть «недошлифованы». Он писалcя с прицелом на сборку/редактирование в среде **ChatGPT-5 (Thinking & Pro modes)** **для ускорения доработок без нагромождения типового кода**. В целях прозрачности весь пайплайн воспроизводим: следуйте ссылкам выше, чтобы повторить анализ и сбор данных с учётом всех оговорённых нюансов и проверить результаты. 

---

> ℹ️ **code-only:** исходные данные вы получаете сами и используете **по условиям их провайдеров**. Этот репозиторий **не** релицензирует чужие данные.

---

## 🔐 Интегрити-артефакты
Инструмент поддерживает выпуск манифеста **SHA-256** `artifacts.sha256` для входных и выходных файлов. По этим дайджестам можно **верифицировать**, что опубликованный результат соответствует заявленным входам (без изменения содержимого файлов).

**Проверка на вашей машине:**
```bash
sha256sum -c artifacts.sha256
# macOS: shasum -a 256 -c artifacts.sha256
```
> Примечание: если строки в манифесте содержат абсолютные пути, это не влияет на корректность хэшей; при необходимости создайте локальную копию манифеста с относительными путями и проверяйте по ней.

---

## ⚖️ Лицензия
**Apache-2.0** (`LICENSE`) — на исходный код в этом репозитории.  
Внешние данные, которыми вы пользуетесь с помощью этих инструментов, остаются под условиями их оригинальных провайдеров.

---

## ✉️ Контакты
GitHub: **@rleydev (thelaziestcat)** · email: **thelaziestcat@proton.me** / **thelazyazzcat@gmail.com**
