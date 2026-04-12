use pyo3::prelude::*;

/// A dummy struct to demonstrate Rust ↔ Python interop.
/// Replace this with real ECS storage later.
#[pyclass]
struct Counter {
    #[pyo3(get)]
    value: i64,

    #[pyo3(get)]
    label: String,
}

#[pymethods]
impl Counter {
    #[new]
    fn new(label: String) -> Self {
        Counter { value: 0, label }
    }

    fn increment(&mut self, amount: i64) {
        self.value += amount;
    }

    fn reset(&mut self) {
        self.value = 0;
    }

    fn __repr__(&self) -> String {
        format!("Counter('{}', value={})", self.label, self.value)
    }
}

/// The Python module. This is what `import tigen_core` gives you.
#[pymodule]
fn tigen_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Counter>()?;
    Ok(())
}
