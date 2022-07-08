function createChartContainer(scaffold, container, chart, options) {
    const chart_node = document.querySelector(scaffold).cloneNode(true)
    chart_node.style.display = "block";
    document.querySelector(container).appendChild(chart_node);
    return chart_node;
}


const toggleNotes = () => {
  const notes = document.getElementsByClassName('dygraph-annotation');
  console.log("notes", notes)
  for (let i = 0; i < notes.length; i++) {
    if (!notes[i].style.display || notes[i].style.display === "block") notes[i].style.display = "none";
    else notes[i].style.display = "block";
  }
}

const formatData = (totalContainers, currentContainer, X, Y) => {
  let arr = [X];
  for (let i = 0; i < totalContainers; i++) {
    if (i === currentContainer) arr.push(Y);
    else arr.push(NaN);
  }
  return arr;
}

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
}

const createGraph = (element, data, labels, title) => {
  return new Dygraph(element,
                        data,
                        {
                          labels,
                          fillGraph: true,
                          rollPeriod: 10,
                          showRoller: true,
                          title,
                                legend: 'always' ,
                                labelsSeparateLines: true,
                          highlightSeriesOpts: { strokeWidth: 2 },
                          // showLabelsOnHighlight: false,
                          axes: {
                            x: {
                              axisLabelFormatter: Dygraph.dateAxisLabelFormatter,
                              ticker: Dygraph.dateTicker,
                            }
                          },
                          drawCallback: function(g) {
                            // const notes = document.getElementsByClassName('dygraph-annotation');
                            // for (let i = 0; i < notes.length; i++) {
                            //   if (notes[i].style.top === "") notes[i].style.display = "none";
                            // }
                          },
                          annotationMouseOverHandler: function(ann, point, dg, event) {
                            let modal = document.getElementById("myModal");
                            modal.style.display = "block";
                            modal.innerHTML = ` <!-- Modal content -->
                                                <div class="modal-content">
                                                  <p>${ann.text}</p>
                                                </div>`
                          },
                          annotationMouseOutHandler: function(ann, point, dg, event) {
                            let modal = document.getElementById("myModal");
                            modal.style.display = "none";
                          },
                        });
}

