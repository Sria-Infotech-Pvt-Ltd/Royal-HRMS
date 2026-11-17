import { describe, expect, it } from "vitest"
import { ASSESSMENT_TEMPLATES, templateById } from "./assessmentTemplates"

describe("assessment templates", () => {
  it("offers a quiz, video training, both together, and a blank start, in that order", () => {
    expect(ASSESSMENT_TEMPLATES.map(template => template.id)).toEqual(["quiz", "video", "mixed", "blank"])
  })

  it("gives every template a distinct id, title and icon", () => {
    for (const key of ["id", "title", "icon"] as const) {
      expect(new Set(ASSESSMENT_TEMPLATES.map(template => template[key])).size).toBe(ASSESSMENT_TEMPLATES.length)
    }
  })

  it("pre-fills a title and description for each real type and leaves the blank one empty", () => {
    for (const template of ASSESSMENT_TEMPLATES.filter(item => item.id !== "blank")) {
      expect(template.formTitle.trim()).not.toBe("")
      expect(template.formDescription.trim()).not.toBe("")
    }
    expect(templateById("blank")).toMatchObject({ formTitle: "", formDescription: "" })
  })

  it("fits the title field the form already enforces", () => {
    for (const template of ASSESSMENT_TEMPLATES) expect(template.formTitle.length).toBeLessThanOrEqual(150)
  })

  it("does not carry a pass mark, attempts or time limit, so those keep coming from Settings", () => {
    for (const template of ASSESSMENT_TEMPLATES) {
      expect(Object.keys(template)).not.toEqual(expect.arrayContaining(["pass_percentage"]))
      expect(Object.keys(template)).not.toEqual(expect.arrayContaining(["max_attempts"]))
    }
  })

  it("finds a template by id and returns nothing for an unknown one", () => {
    expect(templateById("video")?.title).toBe("Video training")
    expect(templateById("nope")).toBeUndefined()
  })
})
