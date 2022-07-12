const setAPIurl = () => {
  if (document.location.host.indexOf('metrics.green-coding.org') === 0)
    api_url = "https://api.green-coding.org";
  else
    api_url = "http://api.green-coding.local:8000";
}

const getAnnotations = (my_json) => {
  console.log("my_json from the notes", my_json)

  // const replicateAnnotations = (target) => {
  //     if (el[2] !== target) { // avoids duplication of annotations on the same chart
  //       if (my_series[target][el[0]] == undefined) {
  //         my_series[target][el[0]] = { name: el[0], data: [{ x: el[1], y: 0 }] }
  //       } else {
  //         my_series[target][el[0]]['data'].push({ x: el[1], y: 0 })
  //       }
  //     }
  //   }

  for (let i = 0; i < my_json.data.length; i++) {
    if (my_json.data[i][1] !== "[SYSTEM]") {
      annotations.push({
        series: my_json.data[i][1],
        x: my_json.data[i][3] / 1000,
        shortText: my_json.data[i][2][0] === " " ? my_json.data[i][2][1] : my_json.data[i][2][0], // first letter of the message; in case it's a space, then seccond letter
        text: my_json.data[i][2],
      })
    }
  }
  // hardcoding annotations' timestamps so that they appear on the graph
  annotations[0].x = 1657294498387.516;
  annotations[1].x = 1657294500298.983;
  console.log("annotations", annotations)
}

const getData = (my_json) => {
  console.log("my_json", my_json)

  document.querySelector("#project-last-crawl").innerText = my_json.project.last_crawl;
  document.querySelector("#project-name").innerText = my_json.project.name;
  document.querySelector("#project-uri").innerText = my_json.project.uri;
  document.querySelector("#project-cpu").innerText = my_json.project.cpu;
  document.querySelector("#project-memtotal").innerText = my_json.project.memtotal;

  my_json.data.forEach(el => {
    if (my_series[el[2]] == undefined) {
      my_series[el[2]] = {}
    }

    // if (el[0] == '[SYSTEM]' && el[4] == '[START MEASUREMENT]') {
    //   accumulate = 1;
    //   return
    // } else if (el[0] == '[SYSTEM]' && el[4] == '[END MEASUREMENT]') {
    //   accumulate = 0;
    //   return;
    // }

    el[1] = el[1] / 1000;

    var value = null;
    // if (el[2] == 'cpu_cgroup' && accumulate === 1) {
    if (el[2] == 'cpu_cgroup') {
      cpu_load.push(el[3]);
      value = el[3] / 100;
    } else if (el[2] == 'energy_system_RAPL_MSR') {
      // if (accumulate === 1)
      total_energy += el[3]
      value = el[3];
    } else if (el[2] == 'memory_cgroup') {
      mem_load.push(el[3])
      value = el[3] / 1000000;
    } else {
      value = el[3];
    }

    if (my_series[el[2]][el[0]] == undefined) {
      my_series[el[2]][el[0]] = { name: el[0], data: [{ x: el[1], y: value }] }
    } else {
      my_series[el[2]][el[0]]['data'].push({ x: el[1], y: value })
    }

    /*
    el[0] // container_id
    el[1] // time
    el[2] // metric name
    el[3] // value
    el[4] // note => Not anymore present
    '*/
  })
}

const displayGraphs = () => {
  let counter = 0; // for automatically creating pair of <div>s
  for (el in my_series) {
    // console.log("el", el)
    if (el !== "null") { // prevents displaying a graph for the container_name "[SYSTEM]" which has all metrics set to "null"
      const { data, labels } = getFormattedDataAndLabels(Object.values(my_series[el]));
      createChartContainer("chart-container", el, counter)
      const chart = createGraph(el, data, labels, el)
      chart.setAnnotations(annotations);
      counter++;
    }
  }
}

const getFormattedDataAndLabels = (series) => {
  let containerX;
  let containerY;
  let data = [];
  let labels = ["Time"];

  for (let i = 0; i < series.length; i++) {
    labels.push(series[i].name || "");
    for (let j = 0; j < series[i].data.length; j++) {
      containerX = series[i].data[j].x;
      containerY = series[i].data[j].y;
      data.push(formatData(series.length, i, containerX, containerY));
    }
  }
  return { data, labels };
};

const formatData = (totalContainers, currentContainer, X, Y) => {
  let arr = [X];
  for (let i = 0; i < totalContainers; i++) {
    if (i === currentContainer) arr.push(Y);
    else arr.push(NaN);
  }
  return arr;
};

const createChartContainer = (container, el, counter) => {
  const chart_node = document.createElement("div")
  chart_node.classList.add("card");
  chart_node.innerHTML = `<div class="content">
                            <div class="description">
                              <div class="chart" id=${el}></div>
                              ${counter === 0 ? `<div>
                                <label>
                                  <input type="checkbox" checked="" onchange="toggleNotes()"><span
                                    style="font-size: 0.8em; margin-left: 2px">Show notes</span>
                                </label>
                              </div>` : ``}
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
    document.getElementById(container).appendChild(twoCards);
    document.getElementById(id).appendChild(chart_node);
    // console.log(`counter ${counter} -> created twoCards div`)
  } else {
    const id = "twoCards" + (counter - 1);
    // console.log(`counter ${counter} -> belongs to already created div with id ${id}`)
    document.getElementById(id).appendChild(chart_node);
  }
  return chart_node;
}

const createGraph = (element, data, labels, title) => {
  // console.log('labels', labels)
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
      const notes = document.getElementsByClassName('dygraph-annotation');
      for (let i = 0; i < notes.length; i++) {
        if (notes[i].style.top === "") notes[i].style.display = "none";
      }
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

const displayStatistics = () => {
  document.querySelector("#max-cpu-load").innerText = (Math.max.apply(null, cpu_load) / 100) + " %"
  document.querySelector("#total-energy").innerText = (total_energy / 1000).toFixed(2) + " J"
  document.querySelector("#total-co2").innerText = (total_energy / 1000 / 3600000 * 0.519 * 1000000).toFixed(2) + " ugCO2eq"
  document.querySelector("#avg-cpu-load").innerText = ((cpu_load.reduce((a, b) => a + b, 0) / cpu_load.length) / 100).toFixed(2) + " %"

  const total_CO2 = (total_energy / 1000 / 3600000 * 0.519 * 1000000);
  // const total_CO2_in_kg = total_CO2 / 1000000000; // the real value, bring it back later on
  const total_CO2_in_kg = total_CO2; // fake value only so that we see numbers greater than 0.00

  document.querySelector("#trees").innerText = (total_CO2_in_kg / 0.06 / 1000).toFixed(2) + " trees";
  document.querySelector("#miles-driven").innerText = (total_CO2_in_kg / 0.000403 / 1000).toFixed(2) + " miles driven";
  document.querySelector("#gasoline").innerText = (total_CO2_in_kg / 0.008887 / 1000).toFixed(2) + " gallons";
  document.querySelector("#smartphones-charged").innerText = (total_CO2_in_kg / 0.00000822 / 1000).toFixed(2) + " smartphones charged";
  document.querySelector("#flights").innerText = (total_CO2_in_kg / 1000).toFixed(2) + " flights from Berlin to New York City";
}

const toggleNotes = () => {
  const notes = document.getElementsByClassName("dygraph-annotation");
  console.log("notes", notes);
  for (let i = 0; i < notes.length; i++) {
    if (notes[i].style.top !== "") { // prevent the broken notes on top to appear again
      if (notes[i].style.display === "" || notes[i].style.display === "block")
        notes[i].style.display = "none";
      else notes[i].style.display = "block";
    }
  }
};