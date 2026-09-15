You are generating a paper-grounded diagram intermediate representation for paper_valt.

Return exactly one JSON object and nothing else. Do not use Markdown fences, comments, or explanatory prose. The object must conform to docs/design/ir-schema.v1.json:

{
  "version": 1,
  "type": "workflow" or "data_flow",
  "title": "short descriptive title",
  "nodes": [
    {
      "id": "stable-kebab-case-id",
      "label": "short name",
      "role": "input|module|loss|data|model|output|eval",
      "detail": "brief detail supported by the source",
      "evidence": {"section": "exact section heading or best source heading", "page": 0, "quote": "exact contiguous substring from the supplied paper text"}
    }
  ],
  "edges": [
    {
      "from": "existing node id",
      "to": "existing node id",
      "label": "relationship or transformation",
      "evidence": {"section": "exact section heading or best source heading", "page": 0, "quote": "exact contiguous substring from the supplied paper text"}
    }
  ],
  "groups": []
}

The user will supply a diagram type and a source-text excerpt after this instruction. Build one compact, directed, acyclic graph from that source only.

Evidence rules are strict:

1. Every node and every edge must contain evidence with all three fields: section, page, and quote.
2. Every quote must be copied character-for-character as one contiguous substring from the supplied source text. Never paraphrase a quote, normalize punctuation, translate it, or invent a citation. Keep each quote at 200 characters or fewer. Prefer 8-180 characters that directly support the item.
3. The source excerpt may not contain reliable PDF page markers. In that case use page 0. Do not guess a positive page number.
4. Use a short heading from the source for section when one is visible; otherwise use "source excerpt".
5. Evidence on an edge must support the relationship itself, not merely one endpoint.
6. If the source does not support a possible node or edge, omit it. Do not fill gaps with general knowledge.

Graph rules:

- For workflow, show the paper's method or inference sequence from inputs through modules to outputs/evaluation. Keep it acyclic and use 3-12 nodes.
- For data_flow, show how data is collected, transformed, filtered, batched, trained, or evaluated. Keep it acyclic and use 3-12 nodes.
- Use at most 20 nodes and 30 edges. Every edge endpoint must be an existing node id. Avoid self-loops and cycles.
- Keep labels and details concise. Do not include claims that lack direct source support.
- Use an empty groups array unless grouping is clearly supported by the source.

Before returning, mentally check that every quote occurs verbatim in the supplied source text, every edge is supported, all ids are unique, and the JSON has no trailing text.
