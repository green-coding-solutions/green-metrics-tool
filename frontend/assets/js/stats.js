function createChartContainer(container, el, counter) {
  console.log("counter", counter)
  const chart_node = document.createElement("div")
  chart_node.id = el;
  chart_node.classList.add("card");
  chart_node.innerHTML = `<div class="content">
                            <div class="description">
                              <div class="chart"></div>
                              <div>
                                <label>
                                  <input type="checkbox" checked="" onchange="toggleNotes()"><span
                                    style="font-size: 0.8em; margin-left: 2px">Show notes</span>
                                </label>
                              </div>
                            </div>
                          </div>
                        `
  
  if (counter % 2 === 0) {
    const twoCards = document.createElement("div");
    twoCards.classList.add("ui");
    twoCards.classList.add("two");
    twoCards.classList.add("cards");
    twoCards.classList.add("stackable");
    const id = "twoCards" + counter;
    twoCards.id = id;
    document.querySelector(container).appendChild(twoCards);
    document.getElementById(id).appendChild(chart_node);
    console.log("created twoCards div")
  } else {
    const id = "twoCards" + (counter - 1);
    console.log("belongs to already created div with id", id)
    document.getElementById(id).appendChild(chart_node);
  }

  return chart_node;
}

function buildOptions(series, annotation, chart_title) {
  const options = {
    series: Object.values(series),
    chart: {
      type: "area",
      animations: {
        enabled: false,
      },
    },
    dataLabels: {
      enabled: false,
    },
    stroke: { curve: "smooth" },
    tooltip: {
      x: { format: "dd/MM/yy HH:mm" },
    },
    xaxis: { tickAmount: 6, type: "datetime" },
    annotations: { xaxis: annotation },
    title: { text: chart_title },
  };

  return options;
}

const toggleNotes = () => {
  const notes = document.getElementsByClassName("dygraph-annotation");
  console.log("notes", notes);
  for (let i = 0; i < notes.length; i++) {
    if (!notes[i].style.display || notes[i].style.display === "block")
      notes[i].style.display = "none";
    else notes[i].style.display = "block";
  }
};

const formatData = (totalContainers, currentContainer, X, Y) => {
  let arr = [X];
  for (let i = 0; i < totalContainers; i++) {
    if (i === currentContainer) arr.push(Y);
    else arr.push(NaN);
  }
  return arr;
};

const getDataAndLabels = (series) => {
  let containerX;
  let containerY;
  let data = [];
  let labels = ["Time"];

  for (let i = 0; i < series.length; i++) {
    labels.push(series[i].name);
    for (let j = 0; j < series[i].data.length; j++) {
      containerX = series[i].data[j].x;
      containerY = series[i].data[j].y;
      data.push(formatData(series.length, i, containerX, containerY));
    }
  }
  return { data, labels };
};

const createGraph = (element, data, labels, title) => {
  return new Dygraph(element, data, {
    labels,
    fillGraph: true,
    rollPeriod: 10,
    showRoller: true,
    title,
    legend: "always",
    labelsSeparateLines: true,
    highlightSeriesOpts: { strokeWidth: 2 },
    // showLabelsOnHighlight: false,
    axes: {
      x: {
        axisLabelFormatter: Dygraph.dateAxisLabelFormatter,
        ticker: Dygraph.dateTicker,
      },
    },
    drawCallback: function (g) {
      // const notes = document.getElementsByClassName('dygraph-annotation');
      // for (let i = 0; i < notes.length; i++) {
      //   if (notes[i].style.top === "") notes[i].style.display = "none";
      // }
    },
    annotationMouseOverHandler: function (ann, point, dg, event) {
      let modal = document.getElementById("myModal");
      modal.style.display = "block";
      modal.innerHTML = ` <!-- Modal content -->
                                                <div class="modal-content">
                                                  <p>${ann.text}</p>
                                                </div>`;
    },
    annotationMouseOutHandler: function (ann, point, dg, event) {
      let modal = document.getElementById("myModal");
      modal.style.display = "none";
    },
  });
};
