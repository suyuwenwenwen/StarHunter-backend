// ==========================================
// 模版3：左侧淡紫侧边栏 + 右侧正文（中文适配版）
// ==========================================
#let data = json("resume_data.json")
#let config = json("resume_config.json")
#let fs = config.at("font_size", default: 10)
#let ls = config.at("line_spacing", default: 1.0)
#let sidebar-fill = rgb("#EDE7F6")   // 清新淡紫
#let sidebar-text = rgb("#4A3A66")   // 深紫，保证浅色底上可读
#let sidebar-accent = rgb("#6A4FA3") // 侧栏标题紫
#let accent = rgb("#6A4FA3")   // 正文标题统一紫色系，与侧栏一致

#set page(paper: "a4", margin: 0pt)
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

// 侧边栏小节标题
#let side-heading(title) = [
  #v(0.8em)
  #text(size: fs * 1.15 * 1pt, weight: "bold", fill: sidebar-accent)[#title]
  #v(0.15em)
  #line(length: 100%, stroke: 0.6pt + rgb("#C3B1E1"))
  #v(0.5em)
]

// 正文小节标题
#let main-heading(title) = [
  #v(0.5em)
  #text(size: fs * 1.3 * 1pt, weight: "bold", fill: accent)[#title]
  #v(0.1em)
  #line(length: 100%, stroke: 0.7pt + accent)
  #v(0.4em)
]

// 正文经历条目
#let entry(title, org, location, date, content) = [
  #grid(columns: (1fr, auto), align: (left, right), [
    #text(weight: "bold")[#title]
    #if org != "" [#h(0.6em) #text(weight: "regular")[#org]]
    #if location != "" [#h(0.8em) #text(fill: gray, size: fs * 0.9 * 1pt)[#location]]
  ], [#text(fill: gray)[#date]])
  #bullet-list(content)
]

#grid(
  columns: (0.34fr, 1fr),
  column-gutter: 0pt,
  // ================= 左侧栏 =================
  block(width: 100%, height: 100%, fill: sidebar-fill)[
    #pad(x: 1.3em, y: 1.8em)[
      #set text(fill: sidebar-text)

      // 姓名
      #text(size: fs * 1.8 * 1pt, weight: "bold")[#data.at("NAME", default: "")]
      #v(0.4em)

      // 联系方式（空项自动隐藏）
      #let contacts = (
        data.at("PHONE", default: ""),
        data.at("EMAIL", default: ""),
        data.at("LOCATION", default: ""),
        data.at("GITHUB", default: ""),
        data.at("LINKEDIN", default: ""),
        data.at("SITE", default: ""),
      ).filter(it => it != "")
      #for c in contacts [
        #c
        #if c != contacts.last() [#v(0.25em)]
      ]

      // 技能特长
      #let sk-pro = data.at("SKILL_PRO", default: "")
      #let sk-tool = data.at("SKILL_TOOL", default: "")
      #let sk-lang = data.at("SKILL_LANG", default: "")
      #if sk-pro != "" or sk-tool != "" or sk-lang != "" [
        #side-heading[技能特长]
        #if sk-pro != "" [#text(weight: "bold")[专业技能] \ #sk-pro #v(0.4em)]
        #if sk-tool != "" [#text(weight: "bold")[工具软件] \ #sk-tool #v(0.4em)]
        #if sk-lang != "" [#text(weight: "bold")[语言能力] \ #sk-lang]
      ]
    ]
  ],
  // ================= 右侧正文 =================
  pad(x: 1.5em, y: 1.8em)[
    // 教育背景（必展示）
    #main-heading[教育背景]
    #let edu-school = data.at("EDU_SCHOOL", default: "")
    #let edu-degree = data.at("EDU_DEGREE", default: "")
    #let edu-location = data.at("EDU_LOCATION", default: "")
    #let edu-date = data.at("EDU_DATE", default: "")
    #grid(columns: (1fr, auto), align: (left, right), [
      #text(weight: "bold")[#edu-school]
      #if edu-degree != "" [#h(0.6em) #text(style: "italic")[#edu-degree]]
      #if edu-location != "" [#h(0.8em) #text(fill: gray, size: fs * 0.9 * 1pt)[#edu-location]]
    ], [#text(fill: gray)[#edu-date]])
    #let edu-courses = data.at("EDU_COURSES", default: "")
    #if edu-courses != "" [- 核心课程：#edu-courses]
    #let edu-awards = data.at("EDU_AWARDS", default: "")
    #if edu-awards != "" [- 荣誉奖项：#edu-awards]

    // 实习经历（必展示，渲染全部经历）
    #main-heading[实习经历]
    #let experiences = {
      let exps = data.at("EXPERIENCES", default: none)
      if exps != none and exps.len() > 0 {
        exps
      } else {
        (
          (company: data.at("EXP_1_COMPANY", default: ""), role: data.at("EXP_1_ROLE", default: ""), location: data.at("EXP_1_LOCATION", default: ""), date: data.at("EXP_1_DATE", default: ""), content: data.at("EXP_1_CONTENT", default: "")),
          (company: data.at("EXP_2_COMPANY", default: ""), role: data.at("EXP_2_ROLE", default: ""), location: data.at("EXP_2_LOCATION", default: ""), date: data.at("EXP_2_DATE", default: ""), content: data.at("EXP_2_CONTENT", default: "")),
        )
      }
    }
    #for e in experiences [
      #if e.at("company", default: "") != "" or e.at("role", default: "") != "" or e.at("content", default: "") != "" [
        #entry(
          e.at("role", default: ""),
          e.at("company", default: ""),
          e.at("location", default: ""),
          e.at("date", default: ""),
          e.at("content", default: ""),
        )
      ]
    ]

    // 校园经历（有内容才显示，支持多条）
    #let campus = {
      let cps = data.at("CAMPUS", default: none)
      if cps != none and cps.len() > 0 {
        cps
      } else {
        (
          (org: data.at("CAMPUS_ORG", default: ""), role: data.at("CAMPUS_ROLE", default: ""), location: data.at("CAMPUS_LOCATION", default: ""), date: data.at("CAMPUS_DATE", default: ""), content: data.at("CAMPUS_CONTENT", default: "")),
        )
      }
    }
    #if campus.any(e => e.at("org", default: "") != "" or e.at("role", default: "") != "" or e.at("content", default: "") != "") [
      #main-heading[校园经历]
      #for e in campus [
        #if e.at("org", default: "") != "" or e.at("role", default: "") != "" or e.at("content", default: "") != "" [
          #entry(
            e.at("org", default: ""),
            e.at("role", default: ""),
            e.at("location", default: ""),
            e.at("date", default: ""),
            e.at("content", default: ""),
          )
        ]
      ]
    ]
  ],
)
