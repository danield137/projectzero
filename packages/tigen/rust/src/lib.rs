use std::collections::HashMap;

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

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Verbosity {
    ERROR,
    WARNING,
    INFO,
    DEBUG,
}

impl From<Verbosity> for i32 {
    fn from(v: Verbosity) -> Self {
        match v {
            Verbosity::ERROR => 1,
            Verbosity::WARNING => 2,
            Verbosity::INFO => 3,
            Verbosity::DEBUG => 4,
        }
    }
}


struct Component {
}

// TODO: A lot of future improvements here:
// 1. Use dense storage (Bitset) instead of Vecs. Requires more memory ahead of time, but much more cache-friendly.
// 2. For reading _while_ mutating, we need to implement a "snapshot" mode. 
/*    IsolationLevel(Enum):
    """
    Enum controlling iteration mode.
    NONE:       Live iteration (all modifications are visible).
    ALLOW_DELETIONS: Fixed-range iteration—new insertions are ignored, deletions show as gaps.
    FULL:       "Immutable" iteration: snapshot range is locked; new insertions are ignored;
                    deletions in indices beyond the current iterator position are deferred.
    """
*/
#[derive(Debug, Clone)]
struct GenerationalContainer<T> {
    free_ids: Vec<u32>,
    data: Vec<Option<T>>,
    generations: Vec<u32>,
    next_id: u32,
}

impl<T> GenerationalContainer<T> {
    fn new() -> Self {
        GenerationalContainer {
            free_ids: Vec::new(),
            data: Vec::new(),
            generations: Vec::new(),
            next_id: 0,
        }
    }

    fn with_capacity(capacity: usize) -> Self {
        GenerationalContainer {
            free_ids: Vec::with_capacity(capacity),
            data: Vec::with_capacity(capacity),
            generations: Vec::with_capacity(capacity),
            next_id: 0,
        }
    }

    fn insert(&mut self, value: T) -> u32 {
        if let Some(free_id) = self.free_ids.pop() {
            let id = free_id as usize;
            self.data[id] = Some(value);
            self.generations[id] = self.generations[id].wrapping_add(1);
            free_id
        } else {
            let id = self.next_id;
            self.data.push(Some(value));
            self.generations.push(0);
            self.next_id += 1;
            id
        }
    }

    fn get(&self, id: u32) -> Option<&T> {
        let id = id as usize;
        if id < self.data.len() {
            self.data[id].as_ref()
        } else {
            None
        }
    }

    fn remove(&mut self, id: u32) -> Option<T> {
        let id = id as usize;
        if id < self.data.len() {
            self.free_ids.push(id as u32);
            self.data[id].take()
        } else {
            None
        }
    }
}


struct ECS {
    next_entity_id: i32,
    entities_by_id: HashMap<i32, String>,//GenerationalDict[int, str],
    entities_by_type: HashMap<String, HashMap<i32, String>>,// dict[str, GenerationalDict[int, Any]],
    components_by_entity:  HashMap<i32, HashMap<String, Component>>, // GenerationalDict[int, dict[str, Component]],
    components_by_type: HashMap<String, HashMap<i32, Component>>, // dict[str, GenerationalDict[int, Component]],
    verbosity: i32 = Verbosity::WARNING.into(),
    immutable_entities: HashSet<i32> = HashSet::new(),
    free_ids: Vec<i32> = Vec::new(),
}

impl ECS {
    fn entity_exists(&self, eid: i32) -> bool {
        self.entities_by_id.contains_key(&eid)
    }

    fn create_entity(
        &mut self,
        etype: String,
        components: Option<Vec<Component>> = None,
        mutable: bool = true,
    ) -> i32 {
        let eid = if let Some(free_id) = self.free_ids.pop() {
            free_id
        } else {
            let eid = self.next_entity_id;
            self.next_entity_id += 1;
            eid
        };
        self.entities_by_id.insert(eid, etype.clone());
        self.entities_by_type.entry(etype.clone()).or_insert_with(HashMap::new).insert(eid, etype);
        if let Some(components) = components {
            for component in components {
                self.add_component(eid, component.name.clone(), component);
            }
        }
        if !mutable {
            self.immutable_entities.insert(eid);
        }
        eid

    }

    fn create_singleton_entity(
        &mut self,
        etype: String,
        components: Option<Vec<Component>> = None,
        mutable: bool = true,
    ) -> i32 {

    }

    fn remove_entity(self, eid: i32) {

    }

    fn add_component(self, eid: i32, comp_name: String, comp_data: Component) {

    }

    fn get_component(self, eid: i32, comp_name: String) -> Option<Component> {

    }

    fn has_component(self, eid: i32, comp_name: String) -> bool {

    }

    fn get_entities_with_component_type(self, component_type: String, etype: Option<String> = None) -> Iterator<i32> {

    }

    fn update_component(self, eid: i32, comp_name: String, comp_data: Component, debug: bool = false) {

    }
    fn get_entity_components(self, eid: i32) -> HashMap<String, Component> {

    }

    fn get_typed_component(self, eid: i32, comp_type: type[T]) -> T {

    }

    fn get_singleton_component(self, comp_type: type[T]) -> T {

    }

    fn update_typed_component(self, eid: int, comp_data: object, debug: bool = False) {

    }
    fn update_typed_singleton_component(self, comp_data: object, debug: bool = False) {

    }

    fn has_typed_component(self, eid: int, comp_type: type[T]) -> bool {

    }

    fn get_entities_with_typed_component(self, comp_type: type[T], etype: str | None = None) -> Iterator[int] {

    }

    fn add_typed_component(self, eid: int, component: Component) {

    }
} 

/// The Python module. This is what `import tigen_rust` gives you.
#[pymodule]
fn tigen_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Counter>()?;
    Ok(())
}
