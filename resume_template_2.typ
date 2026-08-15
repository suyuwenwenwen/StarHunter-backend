// ==========================================
// 模版2：居中页眉 + 通栏正文（中文适配版）
// ==========================================
#let data = json("resume_data.json")
#let config = json("resume_config.json")
#let fs = config.at("font_size", default: 10)
#let ls = config.at("line_spacing", default: 1.0)
#let accent = rgb("#3258b8")

#set page(paper: "a4", margin: (x: 1.6cm, y: 1.6cm))
#set text(size: fs * 1pt, font: ("Noto Sans CJK SC", "SimSun", "Times New Roman"))
#set par(leading: ls * 1em, justify: true)

// 工具函数：把 "- xxx" 文本行渲染成 Typst 列表
#let bullet-list(text) = {
  let lines = text.split("\n").map(l => l.trim()).filter(l => l != "")
  if lines.len() == 0 {
    []
  } else if lines.all(l => l.starts-with("- ")) {
    list(..lines.map(l => l.slice(2)))
  } else {
    text
  }
}

// 区块标题
#let heading(title) = [
  #v(0.5em)
  #text(size: fs * 1.3 * 1pt, weight: "bold", fill: accent)[#title]
  #v(0.1em)
  #line(length: 100%, stroke: 0.7pt + accent)
  #v(0.4em)
]

// 页眉：姓名居中，联系方式左右分列（空项自动隐藏）
#grid(
  columns: (1fr, 1fr, 1fr),
  align: (left, center, right),
  column-gutter: 1em,
  [
    #let left-items = (
      data.at("EMAIL", default: ""),
      data.at("PHONE", default: ""),
    ).filter(it => it != "")
    #left-items.join(linebreak())
  ],
  [
    #text(size: fs * 1.9 * 1pt, weight: "bold")[#data.at("NAME", default: "")]
    #let site = data.at("SITE", default: "")
    #if site != "" [
      #linebreak()
      #text(size: fs * 0.85 * 1pt, fill: gray)[#site]
    ]
  ],
  [
    #let right-items = (
      data.at("GITHUB", default: ""),
      data.at("LINKEDIN", default: ""),
      data.at("LOCATION", default: ""),
    ).filter(it => it != "")
    #right-items.join(linebreak())
  ],
)
#v(0.9em)
#line(length: 100%, stroke: 1.2pt + accent)
#v(0.5em)

// 教育背景（必展示）
#heading[教育背景]
#let edu-school = data.at("EDU_SCHOOL", default: "")
#let edu-location = data.at("EDU_LOCATION", default: "")
#let edu-date = data.at("EDU_DATE", default: "")
#let edu-degree = data.at("EDU_DEGREE", default: "")
#if edu-school != "" or edu-degree != "" or edu-date != "" [
  #grid(columns: (1fr, auto), align: (left, right), [
    #text(weight: "bold")[#edu-school]
    #if edu-degree != "" [#h(0.6em) #text(style: "italic")[#edu-degree]]
    #if edu-location != "" [#h(0.8em) #text(fill: gray, size: fs * 0.9 * 1pt)[#edu-location]]
  ], [#edu-date])
  #let edu-courses = data.at("EDU_COURSES", default: "")
  #if edu-courses != "" [- 核心课程：#edu-courses]
  #let edu-awards = data.at("EDU_AWARDS", default: "")
  #if edu-awards != "" [- 荣誉奖项：#edu-awards]
]

// 实习经历（必展示）
#heading[实习经历]
#let exp1 = (
  company: data.at("EXP_1_COMPANY", default: ""),
  role: data.at("EXP_1_ROLE", default: ""),
  location: data.at("EXP_1_LOCATION", default: ""),
  date: data.at("EXP_1_DATE", default: ""),
  content: data.at("EXP_1_CONTENT", default: ""),
)
#if exp1.company != "" or exp1.role != "" or exp1.content != "" [
  #grid(columns: (1fr, auto), align: (left, right), [
    #text(weight: "bold")[#exp1.role]
    #if exp1.company != "" [#h(0.6em) #text(weight: "regular")[#exp1.company]]
    #if exp1.location != "" [#h(0.8em) #text(fill: gray, size: fs * 0.9 * 1pt)[#exp1.location]]
  ], [#exp1.date])
  #bullet-list(exp1.content)
]

#let exp2 = (
  company: data.at("EXP_2_COMPANY", default: ""),
  role: data.at("EXP_2_ROLE", default: ""),
  location: data.at("EXP_2_LOCATION", default: ""),
  date: data.at("EXP_2_DATE", default: ""),
  content: data.at("EXP_2_CONTENT", default: ""),
)
#if exp2.company != "" or exp2.role != "" or exp2.content != "" [
  #v(0.25em)
  #grid(columns: (1fr, auto), align: (left, right), [
    #text(weight: "bold")[#exp2.role]
    #if exp2.company != "" [#h(0.6em) #text(weight: "regular")[#exp2.company]]
    #if exp2.location != "" [#h(0.8em) #text(fill: gray, size: fs * 0.9 * 1pt)[#exp2.location]]
  ], [#exp2.date])
  #bullet-list(exp2.content)
]

// 校园经历（有内容才显示）
#let campus-org = data.at("CAMPUS_ORG", default: "")
#let campus-content = data.at("CAMPUS_CONTENT", default: "")
#if campus-org != "" or campus-content != "" [
  #heading[校园经历]
  #let campus-role = data.at("CAMPUS_ROLE", default: "")
  #let campus-date = data.at("CAMPUS_DATE", default: "")
  #let campus-loc = data.at("CAMPUS_LOCATION", default: "")
  #grid(columns: (1fr, auto), align: (left, right), [
    #text(weight: "bold")[#campus-org]
    #if campus-role != "" [#h(0.6em) #text(weight: "regular")[#campus-role]]
    #if campus-loc != "" [#h(0.8em) #text(fill: gray, size: fs * 0.9 * 1pt)[#campus-loc]]
  ], [#campus-date])
  #bullet-list(campus-content)
]

// 技能特长（任一非空才显示）
#let sk-pro = data.at("SKILL_PRO", default: "")
#let sk-tool = data.at("SKILL_TOOL", default: "")
#let sk-lang = data.at("SKILL_LANG", default: "")
#if sk-pro != "" or sk-tool != "" or sk-lang != "" [
  #heading[技能特长]
  #if sk-pro != "" [- 专业技能：#sk-pro]
  #if sk-tool != "" [- 工具软件：#sk-tool]
  #if sk-lang != "" [- 语言能力：#sk-lang]
]
