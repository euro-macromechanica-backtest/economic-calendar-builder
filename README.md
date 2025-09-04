# Euro Macromechanica (EMM) Backtest — Economic Calendar Builder 
*economic calendar builder (code-only)*

> 🧭 This repository is part of the **Euro Macromechanica Backtest (EMM)** ecosystem.

---

## ‼️ Read the Euro Macromechanica (EMM) Backtest ecosystem’s main [results/`README.md`](https://github.com/euro-macromechanica-backtest/results/blob/main/README.md)!

---

## 📚 Related ecosystem

- **Backtest results, strategy proof, data‑quality policy (headline/stress), integrity materials** - *[results](https://github.com/euro-macromechanica-backtest/results/)* 
- **Prepared aggregates/data for reproducibility** - *[data-hub](https://github.com/euro-macromechanica-backtest/data-hub/)*
- **Minute-data analysis and normalization toolkit** - *[minute-data-analyzer](https://github.com/euro-macromechanica-backtest/minute-data-analyzer)*

---

## 🧭 Purpose

**economic calendar builder** — collects key macro releases (central banks/statistical offices). 
  Detailed instruction and nuances see [`AUDIT.md`](https://github.com/euro-macromechanica-backtest/results/blob/main/AUDIT.md)
  See also [`data-hub/economic-calendars/README.md`](https://github.com/euro-macromechanica-backtest/data-hub/tree/main/economic_calendars/README.md).


> The code is intentionally lean; some details are lightly polished. It was authored to be compiled/edited in **ChatGPT‑5 (Thinking & Pro modes)** **to accelerate refinements without excessive boilerplate**. For full transparency, the entire pipeline is reproducible: follow the links above to replicate the data analysis and collection—including all noted nuances—and verify the results.

---

> ℹ️ **code-only:** you fetch any real data yourself and use it under the **original providers’ terms**. This repository does **not** re‑license third‑party data.

---

## 🔐 Integrity artifacts
The tool support emitting **SHA‑256** manifests, `artifacts.sha256`, for input and output files. These digests let you **verify** that a published result was produced from the stated inputs (no file‑content changes).

**Verify on your machine:**
```bash
sha256sum -c artifacts.sha256
# macOS: shasum -a 256 -c artifacts.sha256
```
> Note: if manifest lines contain absolute paths, hashes remain valid; when needed, create a local copy with relative filenames and verify against it.

---

## ⚖️ License
**Apache‑2.0** (`LICENSE`) — for the source code in this repository.  
Any external data you use with these tools remains governed by its **original providers’ terms**.

---

## ✉️ Contact
GitHub: **@rleydev (thelaziestcat)** · email: **thelaziestcat@proton.me** / **thelazyazzcat@gmail.com**
