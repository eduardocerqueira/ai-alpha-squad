import { describe, expect, it } from "vitest";
import { classifyDirectorReply } from "./classify";

describe("classifyDirectorReply", () => {
  it.each([
    ["APPROVE", "approve"],
    ["approved", "approve"],
    ["👍", "approve"],
    ["REJECT: no", "reject"],
    ["no", "reject"],
    ["CHANGES: more info", "changes"],
    ["maybe?", "ambiguous"],
  ] as const)("classifies %s as %s", (input, expected) => {
    expect(classifyDirectorReply(input)).toBe(expected);
  });
});
