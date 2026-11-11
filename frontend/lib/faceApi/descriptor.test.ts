import { describe, expect, it } from "vitest";
import { DESCRIPTOR_LENGTH, isValidDescriptor } from "./descriptor";
import { averageDescriptors } from "./qualityGate";

const valid = () => Array.from({ length: DESCRIPTOR_LENGTH }, (_, i) => i * 0.01);

describe("isValidDescriptor (checked before anything is sent for verification)", () => {
  it("accepts exactly 128 finite numbers, as an array or a Float32Array", () => {
    expect(DESCRIPTOR_LENGTH).toBe(128);
    expect(isValidDescriptor(valid())).toBe(true);
    expect(isValidDescriptor(new Float32Array(128).fill(0.5))).toBe(true);
  });

  it("rejects the wrong length", () => {
    expect(isValidDescriptor(valid().slice(0, 127))).toBe(false);
    expect(isValidDescriptor([...valid(), 0.1])).toBe(false);
    expect(isValidDescriptor([])).toBe(false);
  });

  it("rejects NaN and +/-Infinity anywhere in the vector", () => {
    for (const bad of [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]) {
      const v = valid();
      v[0] = bad;
      expect(isValidDescriptor(v)).toBe(false);
      const w = valid();
      w[127] = bad;
      expect(isValidDescriptor(w)).toBe(false);
    }
  });

  it("rejects missing input and non-numbers", () => {
    expect(isValidDescriptor(null)).toBe(false);
    expect(isValidDescriptor(undefined)).toBe(false);
    const v = valid() as unknown as unknown[];
    v[3] = "0.5";
    expect(isValidDescriptor(v as number[])).toBe(false);
  });

  it("catches a poisoned frame: one NaN frame turns the averaged descriptor invalid", () => {
    const poisoned = valid();
    poisoned[10] = Number.NaN;
    const averaged = averageDescriptors([valid(), valid(), poisoned]);
    expect(averaged).toHaveLength(128);
    expect(isValidDescriptor(averaged)).toBe(false);
  });

  it("accepts the average of three clean frames", () => {
    expect(isValidDescriptor(averageDescriptors([valid(), valid(), valid()]))).toBe(true);
  });
});
