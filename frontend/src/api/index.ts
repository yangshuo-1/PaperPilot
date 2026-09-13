import * as ai from "./ai";
import * as annotations from "./annotations";
import * as assets from "./assets";
import * as diagrams from "./diagrams";
import * as discovery from "./discovery";
import * as folders from "./folders";
import * as papers from "./papers";
import * as projects from "./projects";
import * as reader from "./reader";
import * as tags from "./tags";
import * as translation from "./translation";

export * from "./ai";
export * from "./annotations";
export * from "./assets";
export * from "./client";
export * from "./diagrams";
export * from "./discovery";
export * from "./folders";
export * from "./papers";
export * from "./projects";
export * from "./reader";
export * from "./tags";
export * from "./translation";

export const api = { ...ai, ...annotations, ...assets, ...diagrams, ...discovery, ...folders, ...papers, ...projects, ...reader, ...tags, ...translation };
export { getQuickview } from "./assets";
