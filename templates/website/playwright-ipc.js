import { firefox, chromium } from "playwright";
import fs from "fs";
import { execSync } from "child_process";


const defaultProxy = { server: "http://squid:3128" };
const contextOptions = {
  viewport: { width: 1280, height: 800 },
  ignoreHTTPSErrors: true, // <--- disables SSL check as we funnel requests through proxy
  timeout: 5000,
};

function logNote(message) {
  const timestamp = String(BigInt(Date.now()) * 1000000n).slice(0, 16);
  console.log(`${timestamp} ${message}`);
}

async function startFifoReader(fifoPath, callback) {
  function openStream() {
    const stream = fs.createReadStream(fifoPath, { encoding: "utf-8" });
    stream.on("data", (chunk) => callback(chunk.trim()));
    stream.on("end", () => {
      // Writer closed FIFO, reopen it
      openStream();
    });
    stream.on("error", (err) => {
      console.error(err);
      throw err
      // setTimeout(openStream, 100); // reopening is not really an option for us as we run inside container
    });
  }
  openStream();
}


// Test 1 - BRANCH: Launch Branch website with no cookies
async function run(browserName, headless, proxy) {
  let browser = null;
  const launchOptions = { headless, proxy };

  if (browserName === "firefox") {
    browser = await firefox.launch(launchOptions);
  } else {
    browser = await chromium.launch({
      ...launchOptions,
      args: headless ? ["--headless=new"] : [],
    });
  }
  
  let context = await browser.newContext(contextOptions);
  await context.clearCookies();
  let page = await context.newPage()

  execSync(`mkfifo /tmp/playwright-ipc-ready`); // signal that browser is launched
  execSync(`mkfifo /tmp/playwright-ipc-commands`); // create pipe to get commands

  await startFifoReader("/tmp/playwright-ipc-commands", async (data) => {
      if (data == 'end') {
          await browser.close()
          fs.writeFileSync("/tmp/playwright-ipc-ready", "ready", "utf-8");   // signal that browser is ready although
          process.exit(0)
      } else {
          console.log('Evaluating', data);
          await eval(`(async () => { ${data} })()`);
          fs.writeFileSync("/tmp/playwright-ipc-ready", "ready", "utf-8");   // signal that browser is ready for next command
      }
  });

};

// CLI args
const argv = process.argv;
const args = {};
for (let i = 2; i < argv.length; i++) {
  if (argv[i] === "--browser" && argv[i + 1]) {
    args.browser = argv[++i];
  } else if (argv[i] === "--headless" && argv[i + 1]) {
    args.headless = argv[++i].toLowerCase() === "true";
  } else if (argv[i] === "--proxy" && argv[i + 1]) {
    args.proxy = argv[++i] === "null" ? null : { server: argv[i] };
  }
}

await run(
  (args.browser || "chromium").toLowerCase(),
  args.headless !== undefined ? args.headless : true,
  args.proxy !== undefined ? args.proxy : defaultProxy
);

