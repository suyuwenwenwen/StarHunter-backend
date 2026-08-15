#import "@preview/basic-resume:0.2.9": *

// ==========================================
// 1. 简历数据与排版配置（由后端写入）
// ==========================================
#let data = json("resume_data.json")
#let config = json("resume_config.json")
#let fs = config.at("font_size", default: 10)
#let ls = config.at("line_spacing", default: 1.0)

#let name = data.at("NAME", default: "")
#let location = data.at("LOCATION", default: "")
#let email = data.at("EMAIL", default: "")
#let github = data.at("GITHUB", default: "")
#let linkedin = data.at("LINKEDIN", default: "")
#let phone = data.at("PHONE", default: "")
#let personal-site = data.at("SITE", default: "")

#show: resume.with(
  author: name,
  // 空字段会自动隐藏
  location: location,
  email: email,
  github: github,
  linkedin: linkedin,
  phone: phone,
  personal-site: personal-site,
  accent-color: "#3258b8",
  font: ("Noto Sans CJK SC", "SimSun", "Times New Roman"),
  paper: "a4",
  font-size: fs * 1pt,
)

// 行距（基于字号 em 缩放）
#set par(leading: ls * 1em)

// ==========================================
// 2. 工具函数：把 "- xxx" 文本行渲染成 Typst 列表
// ==========================================
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

// 单段经历：整体为空则隐藏，否则渲染（实习经历必展示）
#let work-block(company, role, location, dates, content) = {
  if company == "" and role == "" and content == "" {
    []
  } else [
    #work(company: company, title: role, location: location, dates: dates)
    #bullet-list(content)
  ]
}

// ==========================================
// 3. 教育背景（必展示）
// ==========================================
== 教育背景
#edu(
  institution: data.at("EDU_SCHOOL", default: ""),
  location: data.at("EDU_LOCATION", default: ""),
  dates: data.at("EDU_DATE", default: ""),
  degree: data.at("EDU_DEGREE", default: ""),
)
#let edu-courses = data.at("EDU_COURSES", default: "")
#if edu-courses != "" [- 核心课程：#edu-courses]
#let edu-awards = data.at("EDU_AWARDS", default: "")
#if edu-awards != "" [- 荣誉奖项：#edu-awards]

// ==========================================
// 4. 实习经历（必展示）
// ==========================================
== 实习经历
#work-block(
  data.at("EXP_1_COMPANY", default: ""),
  data.at("EXP_1_ROLE", default: ""),
  data.at("EXP_1_LOCATION", default: ""),
  data.at("EXP_1_DATE", default: ""),
  data.at("EXP_1_CONTENT", default: ""),
)
#work-block(
  data.at("EXP_2_COMPANY", default: ""),
  data.at("EXP_2_ROLE", default: ""),
  data.at("EXP_2_LOCATION", default: ""),
  data.at("EXP_2_DATE", default: ""),
  data.at("EXP_2_CONTENT", default: ""),
)

// ==========================================
// 5. 校园经历（有内容才显示）
// ==========================================
#let campus-org = data.at("CAMPUS_ORG", default: "")
#let campus-content = data.at("CAMPUS_CONTENT", default: "")
#if campus-org != "" or campus-content != "" [
  == 校园经历
  #work(
    company: campus-org,
    title: data.at("CAMPUS_ROLE", default: ""),
    location: data.at("CAMPUS_LOCATION", default: ""),
    dates: data.at("CAMPUS_DATE", default: ""),
  )
  #bullet-list(campus-content)
]

// ==========================================
// 6. 技能特长（任一非空才显示）
// ==========================================
#let sk-pro = data.at("SKILL_PRO", default: "")
#let sk-tool = data.at("SKILL_TOOL", default: "")
#let sk-lang = data.at("SKILL_LANG", default: "")
#if sk-pro != "" or sk-tool != "" or sk-lang != "" [
  == 技能特长
  #if sk-pro != "" [- *专业技能：* #sk-pro]
  #if sk-tool != "" [- *工具软件：* #sk-tool]
  #if sk-lang != "" [- *语言能力：* #sk-lang]
]
