-- 把 Markdown 的围栏 div 转成真正的 LaTeX 环境。
--
-- 为什么需要这个：pandoc 的 LaTeX writer **会静默丢掉围栏 div 的外壳**，
-- 内容留下、wrapper 没了。实测 `::: {.source} ... :::` 输出就是裸的段落，
-- header.tex 里 `\newenvironment{source}` 从来没被调用过 —— 编译不报错，
-- 样式却一直没生效，这种错只会让成品悄悄不对，不会让流水线停下。
--
-- 这里把下列类名映射成同名 LaTeX 环境（定义见 tools/pdf/header.tex）。
-- 增删支持的类型，改 ENVIRONMENTS 一处即可。

local ENVIRONMENTS = {
  cover = true,        -- 封面：单独一页、不出页码、之后页码重置为 1
  backcover = true,    -- 封底：单独一页、不出页码、不重置页码
  source = true,       -- 来源标注：8–9 pt
  placeholder = true,  -- 占位内容：一眼可辨，不伪装成真数
}

-- 递归转换：div 可以嵌套（封面里放占位块是常见写法）。
-- 必须自己往下走 —— pandoc 的过滤器一旦返回了替换值，就不会再进入它的内部，
-- 只处理最外层的话，嵌套的那些会被原样留成裸段落。
local function convert(el)
  local body = pandoc.Blocks({})
  for _, block in ipairs(el.content) do
    if block.t == "Div" then
      body:extend(convert(block))
    else
      body:insert(block)
    end
  end

  for _, class in ipairs(el.classes) do
    if ENVIRONMENTS[class] then
      local wrapped = pandoc.Blocks({ pandoc.RawBlock("latex", "\\begin{" .. class .. "}") })
      wrapped:extend(body)
      wrapped:insert(pandoc.RawBlock("latex", "\\end{" .. class .. "}"))
      return wrapped
    end
  end
  return body
end

function Div(el)
  if FORMAT ~= "latex" then
    return nil
  end
  return convert(el)
end
