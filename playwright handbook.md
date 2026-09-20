# Playwright 使用指南

写给金融专业、编程基础薄弱的人（也就是我自己）。

**本文所有代码都在本机实跑验证过**，可以直接复制。凡是官方文档和实测结果对不上的地方，我都标了「实测」。

环境底细：Windows 11 专业版 + Node v22.23.1 + Playwright 1.63.0 + Microsoft Edge。

---

## 阅读顺序

| 你是想……               | 直接看     |
| ------------------------ | ---------- |
| 先搞清楚这工具值不值得学 | 第 1 节    |
| 赶紧跑起来第一个脚本     | 第 2、3 节 |
| 查某个操作怎么写         | 第 4 节    |
| 抓网页数据做课题         | 第 5 节    |
| 代码报错了               | 第 6 节    |

---

## 1. 它能干什么、什么时候该用、什么时候别用

### 1.1 具体能干什么

| 能力                 | 说人话                                                   |
| -------------------- | -------------------------------------------------------- |
| 打开网页             | 电脑上会弹出一个真的浏览器窗口，跟你手动点开一模一样     |
| 点击、翻页、填表     | 「点下一页」「在搜索框输入股票代码」这类动作，它能替你做 |
| 截图 / 存 PDF        | 把网页存成图片或 PDF，比如留存某天的基金净值页面         |
| 把网页上的数据抠下来 | 页面上的表格、数字，抓出来存成 Excel                     |
| 批量重复             | 上面这些动作，让它在几十个页面上重复跑一遍               |
| 定时跑               | 配合作业系统的计划任务，每天自动抓一次                   |

### 1.2 什么场景该用它

- 数据**只在网页上**，没有下载按钮，也没开放接口。比如某些披露平台、行业网站的历史数据
- 要**批量**重复取数。几十家公司的公告、几十个交易日的净值
- 要**定期留痕**。每天固定时间截一张某页面的图，作为证据链

### 1.3 什么场景没必要用

这一节是防走弯路的。

| 场景                                   | 为什么不用                                                 |
| -------------------------------------- | ---------------------------------------------------------- |
| 网站有「导出 Excel / CSV」按钮         | 点一下的事，写脚本是舍近求远                               |
| 有现成的 API 接口                      | API 给的是干净数据；网页抓的是「从排版里抠」，页面一改就崩 |
| 只抓一两次、数据量很小                 | 手工复制粘贴更快                                           |
| 网站明确反爬、条款禁止                 | 有法律和封号风险，金融数据尤其要注意版权                   |
| 需要登录、且有风控的平台               | 容易被判定异常，账号有风险                                 |
| 目标页面是重度前端应用（比如行情大屏） | 数据不是写在 HTML 里的，抓法完全不同，成本高很多           |

---

## 2. 环境确认

**这台机器已经装好了，不用重装。** 下面这些是实测结果。

| 组件                      | 实测情况                             | 位置                                                             |
| ------------------------- | ------------------------------------ | ---------------------------------------------------------------- |
| Node.js                   | v22.23.1                             | 已装                                                             |
| npm                       | 10.9.8                               | 已装                                                             |
| Playwright                | 1.63.0，**装在全局**           | `C:\Users\王\AppData\Roaming\npm\node_modules`                 |
| Microsoft Edge            | 已装                                 | `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` |
| Playwright 自带浏览器内核 | chromium / firefox / webkit 都已下载 | `%LOCALAPPDATA%\ms-playwright`                                 |

### 必须先知道的坑

Playwright 装在了**全局**，这意味着：直接在你自己的脚本里写 `require('playwright')`，**它会报错说找不到模块**。

这不是你写错了，是 Node.js 默认只在自己周边的文件夹里找模块，不会去全局目录找。

**解决办法**：跑脚本前，先告诉 Node.js 去哪里找。在 PowerShell 里分两行敲：

```powershell
$env:NODE_PATH = "C:\Users\王\AppData\Roaming\npm\node_modules"
node 你的脚本.js
```

第一行是「指路」，只在当前这个窗口有效，窗口一关就失效。所以每次新开 PowerShell 都要重敲一遍。

嫌麻烦的话可以设成永久环境变量，这个改动会写进系统，需要的话再说，我帮你弄。

---

## 3. 第一个脚本：用 Edge 打开网页

新建一个文本文件，命名 `打开网页.js`，把下面整段贴进去：

```js
const { chromium } = require('playwright');

(async () => {
  // 启动 Edge。channel: 'msedge' 表示用系统里已装的 Edge
  const browser = await chromium.launch({ channel: 'msedge', headless: true });

  // 新开一个标签页。viewport 是窗口大小
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // 打开网址。waitUntil: 'domcontentloaded' 表示页面骨架出来就算加载完
  await page.goto('https://www.chinamoney.com.cn/chinese/bkccpr/', {
    waitUntil: 'domcontentloaded',
    timeout: 30000,
  });

  // 把页面标题打印出来
  console.log('页面标题：', await page.title());

  // 截图保存
  await page.screenshot({ path: '整页截图.png' });

  // 用完要关掉，不然进程会一直挂着
  await browser.close();
})();
```

然后跑：

```powershell
$env:NODE_PATH = "C:\Users\王\AppData\Roaming\npm\node_modules"
node 打开网页.js
```

**实测输出**：

```
页面标题： 人民币汇率中间价_美元USD汇率中间价_欧元日元港币汇率中间价_中国货币网
```

同时当前文件夹里会多出一张 `整页截图.png`。

### 看得见窗口，还是后台静默

代码里那行 `headless: true` 就是开关：

| 写法                | 效果                 | 什么时候用                               |
| ------------------- | -------------------- | ---------------------------------------- |
| `headless: true`  | 不弹窗口，在后台跑   | 批量抓数据。看不到过程，但快             |
| `headless: false` | 弹出真实的 Edge 窗口 | 调试。你能亲眼看到它点了哪里、卡在哪一步 |

写脚本卡住的时候，把 `true` 改成 `false`，看着它跑一遍，问题在哪一目了然。**实测两种模式都能正常打开网页。**

---

## 4. 常用操作速查

这一节当字典用，不用背。

### 4.1 截图

```js
// 整页截图（按窗口大小截）
await page.screenshot({ path: '整页.png' });

// 截超长页面（整页从上到下全拍下来，文件会大很多）
await page.screenshot({ path: '超长.png', fullPage: true });

// 只截某一个元素（比如只截那张表格）
await page.locator('table:visible').first().screenshot({ path: '局部.png' });
```

元素级截图**记得加 `:visible`**。实测：不加的话，`.first()` 很可能选中页面上第一个同名元素，而它往往是隐藏的，然后就卡到超时报错。这个坑我踩过。

### 4.2 存 PDF

```js
await page.pdf({ path: '页面.pdf', format: 'A4', printBackground: true });
```

`printBackground: true` 的作用是保留背景色，不加的话存出来是白底黑字，图表会丢颜色。

**实测**：官方文档说 PDF 只能在无头模式（`headless: true`）下生成，但这台机器上**两种模式都成功**，两种都试过，文件正常。

### 4.3 点击、填表、回车

以巨潮资讯网（上市公司公告的官方披露平台）为例：

```js
// 找到搜索框。用 placeholder 文本定位，比用随机类名稳
const box = page.locator('input[placeholder="代码/简称/拼音/关键字"]:visible');

// 填字
await box.first().fill('招商银行');

// 按回车
await box.first().press('Enter');
```

`:visible` 这个后缀很重要。页面上往往有好几个长得一样的输入框，其中大部分是隐藏的，加上它只会选中你能看见的那个。

其他常用写法：

```js
// 点带某个文字的元素
await page.locator('text=资讯').first().click();

// 点 CSS 选择器命中的元素
await page.locator('#su').click();
```

**优先用文字定位。** 网站的类名（`class`）一改版就变，但「下一页」「下载」「更多」这些文字通常几年不动。用文字定位的脚本更耐改版。

### 4.4 等待

这是**最容易出错**的一环。

```js
// 不推荐：死等固定秒数
await page.waitForTimeout(3000);

// 推荐：等到你要的东西真的出现
await page.waitForSelector('table');
await page.waitForFunction(() => document.body.innerText.includes('货币对'));
```

死等固定秒数的毛病是：网慢的时候 3 秒不够，你还是抓空；网快的时候白等 3 秒，几十个页面跑下来浪费大量时间。

**但「等元素出现」也有讲究**，第 5 节会讲一个真实踩过的坑。

### 4.5 抓文字

```js
// 抓某个元素的文字。元素不存在会直接报错，拿不准就先 .count() 看看有几个
const title = await page.locator('h1').first().innerText();

// 一次性抓一批（在页面里执行，比来回通信快得多）
const items = await page.evaluate(() =>
  [...document.querySelectorAll('h3 a')].map((a) => a.innerText.trim())
);
console.log(items);
```

---

## 5. 抓数据存 Excel

这一节是重点，也是你课题最用得上的部分。

### 5.1 完整例子：抓人民币汇率中间价

数据源：中国货币网（中国外汇交易中心官网），页面上是一张「货币对 / 中间价 / 涨跌」的表格。

```js
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage();

  await page.goto('https://www.chinamoney.com.cn/chinese/bkccpr/', {
    waitUntil: 'domcontentloaded',
    timeout: 30000,
  });

  // 关键：等到「数据行真的出现」，而不是「表格存在」。原因见 5.3
  await page.waitForFunction(
    () => {
      const table = [...document.querySelectorAll('table')].find((t) =>
        t.innerText.includes('货币对')
      );
      return !!table && table.querySelectorAll('tr').length > 5;
    },
    { timeout: 30000 }
  );

  // 把表格读成二维数组：第一层是行，第二层是每行的格子
  const rows = await page.evaluate(() => {
    const table = [...document.querySelectorAll('table')].find((t) =>
      t.innerText.includes('货币对')
    );
    return [...table.querySelectorAll('tr')].map((tr) =>
      [...tr.children].map((td) => td.innerText.trim().replace(/\s+/g, ' '))
    );
  });

  await browser.close();

  // 存成 CSV
  const csv = rows
    .map((row) => row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(','))
    .join('\r\n');
  fs.writeFileSync('人民币汇率中间价.csv', '\uFEFF' + csv, 'utf8');

  console.log('已保存，共', rows.length, '行');
})();
```

**实测输出**：

```
已保存，共 26 行
```

生成的 `人民币汇率中间价.csv` 双击就能用 Excel 打开，长这样：

```
"货币对","中间价","涨跌"
"美元/人民币","6.7743","23.00"
"欧元/人民币","7.8367","79.00"
"100日元/人民币","4.3614","195.00"
"港元/人民币","0.86384","2.90"
```

### 5.2 为什么是 CSV，不是 .xlsx

真正的 `.xlsx` 文件需要额外装一个库。CSV 是纯文本表格，Excel 能直接打开、能直接另存为 xlsx，格式也不丢。

对课题来说，CSV 够用了，还少装一个依赖。真需要 `.xlsx` 再说。

**`\uFEFF` 那三个字符千万别删。** 它是给 Excel 看的「这是 UTF-8 编码」的暗号。不加的话，Excel 用系统默认编码去读，中文会变成一堆乱码。这是个非常经典的坑，我实测确认必须加。

### 5.3 一个真实踩过的坑：表头出来了，数据还没来

这是我在写这份文档时**真的踩到**的。

这个页面是「先出表头，再慢慢填数据」。我一开始写的是「等表格出现就开始抓」，结果抓到的东西只有 1 行 —— 光秃秃一个表头。

第一次还遇到了更迷惑的现象：同一段代码，前面跑通过（抓到 26 行），过一会儿再跑直接超时报错。查下来是**短时间内连续请求同一个网站，被临时限流了**。

两个教训：

1. **要等的是「你要的数据」，不是「页面结构」。** 等 `table` 存在没用，得等行数够多。
2. **别连着猛请求同一个网站。** 批量抓的时候，每个页面之间停一两秒。被限流的表现就是突然超时，隔几分钟又自己好了。

### 5.4 批量抓：加个重试

批量跑的时候，总会有几个页面偶发失败。加一层重试，比手动补跑省事：

```js
async function 抓取页(page, url, 重试次数 = 3) {
  for (let i = 1; i <= 重试次数; i++) {
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForFunction(
        () => {
          const t = [...document.querySelectorAll('table')].find((x) =>
            x.innerText.includes('货币对')
          );
          return !!t && t.querySelectorAll('tr').length > 5;
        },
        { timeout: 30000 }
      );
      return true;
    } catch (e) {
      console.log(`第 ${i} 次失败：${e.message.split('\n')[0]}`);
      if (i === 重试次数) return false;
      await page.waitForTimeout(3000); // 失败后停 3 秒再试
    }
  }
}
```

### 5.5 进阶：用搜索框批量找公告

巨潮资讯网有几千家上市公司的公告。下面这段是**实测跑通**的，搜「招商银行」返回 2256 条：

```js
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

await page.goto('http://www.cninfo.com.cn/new/fulltextSearch', {
  waitUntil: 'domcontentloaded',
  timeout: 40000,
});
await page.waitForTimeout(5000);

const box = page.locator('input[placeholder="代码/简称/拼音/关键字"]:visible');
await box.first().fill('招商银行');
await box.first().press('Enter');

// 等搜索结果出来
await page.waitForSelector('text=搜索结果', { timeout: 30000 });
```

把 `'招商银行'` 换成别的代码或简称，循环一遍就是批量。

---

## 6. 报错怎么说人话

下面每一条，都是我在本机**真跑出来的原始报错**，不是编的。

### 6.1 `Error: Cannot find module 'playwright'`

```
Error: Cannot find module 'playwright'
```

**说人话**：Node.js 在自己周边文件夹里翻遍了，没找到这个工具包。

**怎么办**：十有八九是忘了设路径。跑脚本前先敲：

```powershell
$env:NODE_PATH = "C:\Users\王\AppData\Roaming\npm\node_modules"
```

### 6.2 `locator resolved to hidden` —— 元素找到了，但它是隐形的

```
page.waitForSelector: Timeout 15000ms exceeded.
  - waiting for locator('#kw') to be visible
  - locator resolved to hidden <input id="kw" .../>
```

**说人话**：定位到了，代码没写错。但这个元素在页面上是看不见的（可能被折叠了、宽高是 0、或者网站故意藏起来防自动化）。

**怎么办**：

- 先在代码里打印它到底多大，确认是不是真隐藏：

  ```js
  console.log(await page.locator('#kw').boundingBox()); // 输出 null 就是隐形
  ```
- 换一个能看见的元素来定位，或者用 `:visible` 后缀筛掉隐藏的
- 有些网站（比如百度首页）专门针对自动化做了处理，这种情况换个数据源，别硬啃

### 6.3 `page.fill: Timeout 30000ms exceeded`

```
page.fill: Timeout 30000ms exceeded.
```

**说人话**：想往输入框里打字，但等不到这个框出现，或者等到的框点不了、打不了字。

**怎么办**：

- 确认定位符对不对。用浏览器按 F12，右键那个输入框选「检查」，看看它的 id、placeholder 到底叫什么
- 加上 `:visible` 排除隐藏的同类元素
- 页面是前端框架渲染的话，等久一点，或用 `waitForSelector` 先等它出来

### 6.4 抓到的数据只有表头，没有内容

这个**不会报错**，最阴险 —— 程序跑完了，显示「成功」，打开文件一看是空的。

**说人话**：页面先出表头、后填数据，你抓早了。

**怎么办**：别等「表格存在」，等「数据行数够多」：

```js
await page.waitForFunction(
  () => {
    const t = [...document.querySelectorAll('table')].find((x) => x.innerText.includes('货币对'));
    return !!t && t.querySelectorAll('tr').length > 5;  // 这个 5 按实际数据量调
  },
  { timeout: 30000 }
);
```

把 `5` 改成「少于这个数就不正常」的值。比如你有 20 行数据，就写 `> 10`。

### 6.5 同一段代码，刚才还行，现在突然超时

**说人话**：大概率是被网站临时限流了 —— 你短时间内请求太多次。

**怎么办**：

- 别急着改代码，等三五分钟再跑，往往自己就好了
- 批量抓的时候，每个页面之间 `await page.waitForTimeout(2000)` 停一下
- 加上第 5.4 节那个重试机制

### 6.6 找不到 Edge

**说人话**：`channel: 'msedge'` 让 Playwright 去系统里找 Edge，没找到。

**怎么办**：

- 确认 Edge 装在哪。本机实测在 `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
- 实在不行就用 Playwright 自带的内核，把 `{ channel: 'msedge', headless: true }` 改成 `{ headless: true }`，它会用自己下载的 Chromium，效果基本一样

---

## 附：红线

这份指南教你的是技术，怎么用要有分寸。

- **先看网站的 robots.txt 和使用条款**，明确禁止抓的别抓
- **金融数据注意版权**，有些数据源头就声明了不得转载，抓下来自己研究可以，别二次分发
- **别把账号密码写进脚本**。需要登录的页面，密钥从环境变量取，不要硬编码在代码里
- **控制请求频率**，别把人家网站搞挂，也别让自己被封

---

## 附：完整跑通记录

写这份文档时，在本机实测通过的功能清单：

| 功能                                               | 结果                    |
| -------------------------------------------------- | ----------------------- |
| Edge 无头模式启动                                  | 通过                    |
| Edge 有头模式启动（弹出真实窗口）                  | 通过                    |
| 打开网页、读取标题                                 | 通过                    |
| 整页截图                                           | 通过                    |
| 元素级截图                                         | 通过                    |
| 存 PDF（无头模式）                                 | 通过                    |
| 存 PDF（有头模式，官方文档说不行，实测可以）       | 通过                    |
| 抓表格 → CSV（26 行人民币汇率中间价，中文不乱码） | 通过，连跑 3 次稳定     |
| 填搜索框 + 回车（巨潮资讯网，返回 2256 条）        | 通过                    |
| 遭遇网站临时限流并恢复                             | 已复现，第 5.3 节有记录 |
