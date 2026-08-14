#import "@preview/basic-resume:0.2.9": *

// ==========================================
// 1. 简历数据统一从 resume_data.json 读取
//    （与后端 /api/compile 配套：后端先把结构化数据写入该 JSON）
// ==========================================
#let data = json("resume_data.json")

#let name = data.at("NAME", default: "")
#let location = data.at("LOCATION", default: "")
#let email = data.at("EMAIL", default: "")
#let github = data.at("GITHUB", default: "")
#let linkedin = data.at("LINKEDIN", default: "")
#let phone = data.at("PHONE", default: "")
#let personal-site = data.at("SITE", default: "")

#show: resume.with(
  author: name,
  // 空字段会自动隐藏，无需手动注释
  location: location,
  email: email,
  github: github,
  linkedin: linkedin,
  phone: phone,
  personal-site: personal-site,
  accent-color: "#3258b8",
  font: ("Times New Roman", "SimSun"),
  paper: "a4",
)

// ==========================================
// 2. 工具函数：把 "- xxx" 文本行渲染成 Typst 列表
//    （兼容 AI 生成的分点文案，避免把 "-" 当纯文本输出）
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

// ==========================================
// 3. 教育背景
// ==========================================
== 教育背景
#edu(
  institution: data.at("EDU_SCHOOL", default: ""),
  location: data.at("EDU_LOCATION", default: ""),
  dates: data.at("EDU_DATE", default: ""),
  degree: data.at("EDU_DEGREE", default: ""),
)
- 核心课程：#data.at("EDU_COURSES", default: "")
#let edu-awards = data.at("EDU_AWARDS", default: "")
#if edu-awards != "" [- 荣誉奖项：#edu-awards]

// ==========================================
// 4. 实习经历
// ==========================================
== 实习经历
#work(
  company: data.at("EXP_1_COMPANY", default: ""),
  title: data.at("EXP_1_ROLE", default: ""),
  location: data.at("EXP_1_LOCATION", default: ""),
  dates: data.at("EXP_1_DATE", default: ""),
)
#bullet-list(data.at("EXP_1_CONTENT", default: ""))

#work(
  company: data.at("EXP_2_COMPANY", default: ""),
  title: data.at("EXP_2_ROLE", default: ""),
  location: data.at("EXP_2_LOCATION", default: ""),
  dates: data.at("EXP_2_DATE", default: ""),
)
#bullet-list(data.at("EXP_2_CONTENT", default: ""))

// ==========================================
// 5. 校园经历
// ==========================================
== 校园经历
#work(
  company: data.at("CAMPUS_ORG", default: ""),
  title: data.at("CAMPUS_ROLE", default: ""),
  location: data.at("CAMPUS_LOCATION", default: ""),
  dates: data.at("CAMPUS_DATE", default: ""),
)
#bullet-list(data.at("CAMPUS_CONTENT", default: ""))

// ==========================================
// 6. 技能特长
// ==========================================
== 技能特长
- *专业技能：* #data.at("SKILL_PRO", default: "")
- *工具软件：* #data.at("SKILL_TOOL", default: "")
- *语言能力：* #data.at("SKILL_LANG", default: "")
