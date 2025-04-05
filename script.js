let headers = new Headers();

headers.append('Access-Control-Allow-Origin', 'http://localhost:8080');
headers.append('Access-Control-Allow-Origin', 'http://127.0.0.1:5000/data');
headers.append('Access-Control-Allow-Methods','POST');
headers.append('Access-Control-Allow-Credentials', 'true');

let fileInput = "";
let file = "";
let server_response = "";
let curr_token_count = 0;
let session_token_count = 0;

function submit_file() {
    fileInput = document.getElementById('my_file');
    file = fileInput.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(event) {
            const csvContent = event.target.result;
            displayCSV(csvContent);
            fileInput = parseCSV(csvContent);
        };
        reader.readAsText(file);
    } else {
        alert('Please select a file first.');
    }
}

function displayCSV(csvContent) {
    const rows = csvContent.split('\n');
    let table = '<table>';
    
    rows.slice(0,100).forEach((row, index) => {
        const cells = row.split(',');
        table += '<tr>';
        cells.forEach(cell => {
            if (index === 0) {
                table += `<th>${cell}</th>`;
            } else {
                table += `<td>${cell}</td>`;
            }
        });
        table += '</tr>';
    });

    table += '</table>';
    document.getElementById('csvtable').innerHTML = table;
}

function parseCSV(csvContent) {
    const rows = csvContent.split('\n');
    const headers = rows[0].split(',');
    return rows.slice(1).map(row => {
        const values = row.split(',');
        return headers.reduce((obj, header, index) => {
            obj[header] = values[index];
            return obj;
        }, {});
    });
}

function visualize_graph() {
    const code = document.getElementById('plotlyjs').value;
    try {
        const func = new Function('fileInput', code);
        func(fileInput);
    } catch (error) {
        console.error('Error executing code:', error);
        alert('There was an error executing the code. Check the console for details.');
    }
}

function showLoading() {
    document.getElementById("loading-icon").style.display = "block";
    console.log("ICON SHOW");
}

// Hide loading icon when response is received
function hideLoading() {
    document.getElementById("loading-icon").style.display = "none";
    console.log("ICON HIDE");
}

function App() {
    
    const url = " http://127.0.0.1:5000/data";
    const xhttp = new XMLHttpRequest();

    var ele = document.getElementById('graph-container');
    var result = document.getElementById('result');

    ele.style.display = "none";

    var data_head = fileInput;
    var json_data = JSON.stringify(data_head, null, 2);

    var user_prompt = document.getElementById("user_prompt").value;

    const blob = new Blob([json_data, user_prompt], { type: 'application/json' });

    var retryCount = 0;
    const maxRetries = 2;
    
    // function fetchGraph() {
    //     fetch("graph.json")
    //         .then((response) => {
    //             if (response.ok) {
    //                 console.log("Response Received!!");
    //                 return response.json();
    //             } else {
    //                 throw new Error("Cannot fetch graph.json");
    //             }
    //         })
    //         .then((plot_data) => {
    //             console.log("Plot Data >>", plot_data);
    //             try {
    //                 Plotly.react(ele, plot_data.data, plot_data.layout);
    //                 if(ele.innerHTML === "..." && retryCount < maxRetries){
    //                     retryCount+=1;
    //                     console.log(`Retrying... (${retryCount}/${maxRetries})`);
    //                     fetchGraph();
    //                 }
    //             } catch (err) {
    //                 console.error("Error while Plotting >> ", err);
    //                 //ele.innerHTML = 'Error While Plotting... Please Try again';
    //             }
    //         })
    //         .catch((error) => {
    //             console.error("Error: ", error);
    //             ele.innerHTML = 'Error Fetching Graph';
    //             if(retryCount < maxRetries){
    //                 retryCount+=1;
    //                 console.log(`Retrying... (${retryCount}/${maxRetries})`);
    //                 fetchGraph();
    //             }
                
    //         });
    // }
    xhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            var res = JSON.parse(this.responseText);
            console.log("RES >> ", res);
        result.innerHTML += marked.parse(res["insight"]);
        curr_token_count = Number(res["cost"]);
        session_token_count += curr_token_count;
        result.style.display = "block";
        hideLoading();
        if (res["plot"] != "none") {
            ele.style.display = "block";
            var plot_data = res["plot"];
            Plotly.react(ele, plot_data.data, plot_data.layout);
        } else {
            Plotly.purge(ele);
            ele.style.display = "none";
            } 
        }
        else {
                showLoading();
                result.style.display = "none";
                ele.style.display = none;
            }

    };
    /* xhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200){
            var res = JSON.parse(this.responseText);
            var ele = document.getElementById('graph-container');
            console.log("RES >> ", res);
            result.innerHTML = marked.parse(res["insight"]);
            console.log("Code >> ", "code" in res);
            if (res["insight"].includes("graph.json")){
                // checkGraphFile();
                fetch("graph.json")
                    .then((response) => {
                        if(response.ok){
                            console.log("Response Received!!");
                            return response.json();
                        }
                        else {
                            console.log("Cannot fetch graph.json");
                        }
                    })
                    .then((plot_data) => {
                        console.log("Plot Data >>", plot_data);
                        try {
                            Plotly.plot(ele, plot_data.data, plot_data.layout);
                        }
                        catch(err) {
                            console.error("Error while Plotting >> ", err);
                            ele.innerHTML = 'Error While Plotting... Please Try again';
                        }
                    })
                    .catch((error) => {
                        console.error("Error: ", error)
                        ele.innerHTML = 'Error While Plotting... Please Try again';
                    })

            } else {
                ele.innerHTML = '';
            }
        }
        else {
            result.innerHTML = "Waiting for Response";
            document.getElementById('graph-container').innerHTML = '';
        }
    } */
        xhttp.open("POST", url, true);
        xhttp.setRequestHeader('content-type', 'application/x-www-form-urlencoded;charset=UTF-8');
        xhttp.send(blob);
        console.log(result.innerHTML);
    
    
}

function parseMarkdown(insights) {
    let htmlText = insights
            .replace(/^### (.*$)/gim, '<h5>$1</h5>')
            .replace(/^## (.*$)/gim, '<h4>$1</h4>')
            .replace(/^# (.*$)/gim, '<h3>$1</h3>')
            .replace(/\*\*(.*)\*\*/gim, '<b>$1</b>')
            .replace(/\*(.*)\*/gim, '<i>$1</i>')
            .replace(/\[(.*?)\]\((.*?)\)/gim, '<a href="$2">$1</a>')
            .replace(/```python\n([\s\S]*?)```/gim, '<pre><code class="python">$1</code></pre>')
            .replace(/\n$/gim, '<br />');


    return htmlText;
}

/* function checkGraphFile() {
    fetch('graph.html')
        .then(response => {
            if (response.ok) {
                document.getElementById('graph-container').innerHTML = '<iframe src="graph.html" width="100%" height="500px"></iframe>';
            } else {
                console.log('graph.html does not exist.');
            }
        })
        .catch(error => {
            console.error('Error fetching graph.html:', error);
        }
        );
} */


function token_counter() {
    const modal = document.getElementById('tokenModal'); // Replace with actual token usage value
    document.getElementById('totalTokenUsage').textContent = `Current Session Total Cost: ${session_token_count}`;
    document.getElementById('latestTokenUsage').textContent = `Recent Query Cost: ${curr_token_count}`;
    modal.style.display = 'block';
}

function close_counter() {
    const modal = document.getElementById('tokenModal');
    modal.style.display = 'none';
}

window.addEventListener('click', function(event) {
    const modal = document.getElementById('tokenModal');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
});


        