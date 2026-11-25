# Piping Hydraulics & Temperature Drop Builder

Interactive piping network builder (single `index.html`) with Python engines, hosted on Streamlit.

```
repository/
└── pipingsizing/
    ├── app.py           # Streamlit host - bridges index.html <-> Python, report & downloads
    ├── index.html       # Interactive UI: inputs, piping canvas, validation, results, profile chart
    ├── hydraulics.py    # Units, pipe data, fluids, friction factor, Darcy-Weisbach, Bernoulli, solver
    ├── thermal.py       # Heat loss through insulation, Joule-Thomson / friction heating
    ├── requirements.txt
    └── README.md
```

## Run locally
```bash
cd pipingsizing
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud
1. Push the repo to GitHub.
2. New app -> pick the repo -> **Main file path:** `pipingsizing/app.py`.
   (Cloud reads `requirements.txt` from the same folder as the entry point.)

## How the pieces talk
`app.py` registers `index.html` as a Streamlit custom component
(`components.declare_component(path=<this folder>)`) - no npm build needed.
`index.html` speaks the component protocol directly via `postMessage`:

1. Streamlit sends the catalogue (fluids, units, NPS/schedules, fittings, insulation) -> UI is data-driven.
2. User builds the tree and presses **Calculate** -> `index.html` sends the network JSON.
3. `app.py` calls `hydraulics.solve()` (which calls `thermal.py` every pipe step) and sends results back.
4. `index.html` colours the canvas by pressure, shows ΔP feasibility, the axial profile and segment table.
   Streamlit adds Plotly charts plus CSV / JSON downloads below the builder.

Opening `index.html` directly (e.g. GitHub Pages) still lets you build and export a network, but calculation needs Python.

## Rules enforced
- Size mismatch (e.g. 6" -> 4" without a reducer) -> red alert, Add/Calculate blocked.
- Every branch end must be closed by an **Outlet**. After a tee, outlet flows must close the mass balance
  (one outlet may be left blank = remainder).
- **ΔP not feasible** when pressure reaches vacuum, drops below vapour pressure (liquids), flow chokes (gas Mach ≥ 1),
  or an outlet arrives below its optional minimum required pressure.

## Method & assumptions
- Single-phase, steady flow; tree networks with specified outlet flows (no loops).
- Darcy f: 64/Re laminar, Colebrook-White turbulent, linear blend 2300-4000.
- Fittings: Crane TP-410 `K = n·f_T`; reducers by Crane contraction/expansion formulae.
- Pipes are integrated in up to 200 steps (400 for gas) so density, velocity and temperature update along the line.
- Heat loss: inside film (Gnielinski), wall, insulation, outside (Churchill-Chu / Churchill-Bernstein + radiation) or buried (shape factor).
- Built-in fluid properties are engineering approximations - verify critical cases with CoolProp or your simulator.
- Canvas is a 2D elevation sketch: pipe lengths are drawn on a log scale, branches may overlap visually.
