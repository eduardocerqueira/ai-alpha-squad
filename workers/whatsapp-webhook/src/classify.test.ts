import { describe, expect, it } from "vitest";
import { classifyDirectorReply, formatAuditComment } from "./classify";

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

describe("formatAuditComment", () => {
  it("embeds director and agent avatars", () => {
    const body = formatAuditComment({
      receivedAt: "2026-05-31T12:00:00Z",
      classification: "approve",
      message: "APPROVE",
      agent: "business-owner",
    });
    expect(body).toContain("director.svg");
    expect(body).toContain("business-owner.svg");
    expect(body).toContain("<table>");
  });
});
