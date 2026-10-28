import { describe, expect, it } from "vitest";
import { rowsOf } from "./listResponse";

describe("rowsOf", () => {
  it("reads a plain array", () => expect(rowsOf<number>([1, 2])).toEqual([1, 2]));
  it("reads a paged body", () => expect(rowsOf<number>({ results: [3] })).toEqual([3]));
  it("returns an empty list for anything else", () => {
    expect(rowsOf(undefined)).toEqual([]);
    expect(rowsOf({ count: 0 })).toEqual([]);
    expect(rowsOf(null)).toEqual([]);
  });
});
