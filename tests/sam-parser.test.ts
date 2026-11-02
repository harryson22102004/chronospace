import { describe, expect, it } from "vitest";
import {
  decodeMaskToRaster,
  parseImageStream,
  recordsOfKind,
  type ResponsesEvent,
} from "@meta-sam/parser";
import { closerMeansHigherZ, planeSize } from "../lib/geometry";
import { parseScenePlan } from "../lib/meta";

const SAMPLE =
  "<0f>0<|box;x1=211;y1=228;x2=270;y2=254;w=320;h=334|>" +
  "<|mask;x=0;y=0;data=27,60,~!!!!M!0c[0o91w?q1!pIH4pPRVp2B3'7`e.ioeAf6-k/#Xd8%dX9x(|>" +
  ",2<|box;x1=155;y1=228;x2=202;y2=254;w=320;h=334;c=0.5|>" +
  "<|mask;x=0;y=0;c=0.5;data=27,48,~!!!!J!0c[q=Pj_zs=*4C4(/./x#:/`S_GnD`=o3?X{emCgO$y@|>\n";

async function* events(text: string): AsyncGenerator<ResponsesEvent> {
  const split = Math.max(1, Math.floor(text.length / 2));
  yield {
    type: "response.output_text.delta",
    item_id: "message-1",
    output_index: 0,
    content_index: 0,
    delta: text.slice(0, split),
  };
  yield {
    type: "response.output_text.delta",
    item_id: "message-1",
    output_index: 0,
    content_index: 0,
    delta: text.slice(split),
  };
  yield {
    type: "response.output_text.done",
    item_id: "message-1",
    output_index: 0,
    content_index: 0,
    text,
  };
  yield { type: "response.completed" };
}

async function* completed(text: string): AsyncGenerator<ResponsesEvent> {
  yield {
    type: "response.output_text.done",
    item_id: "message-1",
    output_index: 0,
    content_index: 0,
    text,
  };
  yield { type: "response.completed" };
}

describe("SAM 3.1 parser", () => {
  it("keeps sparse object ids and aligns boxes to image dimensions", async () => {
    const result = await parseImageStream(events(SAMPLE)).finalResult;
    expect(result.outcome.status).toBe("completed");
    const masks = recordsOfKind(result.records, "mask");
    const boxes = recordsOfKind(result.records, "box");
    expect(masks.map((mask) => mask.objectId)).toEqual(["0", "2"]);
    expect(boxes[0]).toMatchObject({ left: 211, top: 228, right: 271, bottom: 255 });
    expect(masks[0].mask.width).toBe(60);
    expect(masks[0].mask.height).toBe(27);
    const raster = decodeMaskToRaster(masks[0].mask);
    expect(raster.length).toBe(27 * 60);
    expect([...new Set(raster)].every((value) => value === 0 || value === 1)).toBe(true);
    expect(masks[1].confidence).toBe(0.5);
    expect(masks[0].confidence).toBeUndefined();
  });

  it("treats an empty lane as a completed segmentation with no records", async () => {
    const result = await parseImageStream(completed("")).finalResult;
    expect(result.outcome.status).toBe("completed");
    expect(result.records).toHaveLength(0);
  });

  it("rejects a truncated mask instead of inventing pixels", async () => {
    const truncated = SAMPLE.replace("Xd8%dX9x(", "Xd8");
    const result = await parseImageStream(completed(truncated)).finalResult;
    const masks = recordsOfKind(result.records, "mask");
    expect(masks.find((mask) => mask.objectId === "0")).toBeUndefined();
    expect(result.diagnostics.some((item) => item.severity === "error")).toBe(true);
  });
});

describe("scene plan and geometry", () => {
  it("rejects unstructured model text", () => {
    expect(parseScenePlan("a cozy room")).toBeNull();
    expect(parseScenePlan(JSON.stringify({ summary: "short" }))).toBeNull();
    const plan = parseScenePlan(
      JSON.stringify({ title: "Room", summary: "A window and a dark corner are visible.", audio: ["clock", "nope"] }),
    );
    expect(plan?.audio).toEqual(["clock"]);
    expect(plan?.title).toBe("Room");
  });

  it("moves higher normalized depth toward the camera", () => {
    expect(closerMeansHigherZ(1, 0.4)).toBeGreaterThan(closerMeansHigherZ(0.2, 0.4));
    expect(planeSize(960, 640).height).toBeCloseTo(1.7 * (640 / 960));
  });
});
