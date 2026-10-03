Using only this paper, produce 3-5 concise Chinese takeaways.
Each takeaway must be exactly one atomic claim: one subject, one predicate, and no joined claims, benchmark comparisons, causal explanations, or speculation.
The content must be directly and completely supported by its citation quote; if a quote supports only part of the claim, rewrite the content down to that part.
Do not add facts implied only by surrounding pages.

Return strict JSON like:

{"takeaways":[{"content":"一个原子结论","citation":{"page":1,"quote":"exact text directly supporting the whole content"}}]}

Rules:
- Use `citation` (singular) or `citations` (plural); entries may only contain the fields `page` and `quote`.
- Quotes must be copied verbatim from the paper; a takeaway without a verifiable quote is discarded.
- No Markdown fences, no comments, no extra fields.

The caller appends the paper context after this instruction.
