# Operating System Laboratory Mini Project (Experiment 9)
### Department of Computer Engineering | JSPM's RSCOE Pune
**Course:** CS2303L – Operating System Laboratory  
**Topic:** Multithreading-Based Application for Efficient Resource Utilization and Task Execution  

---

## 🚀 Quick Start Guide

### 1. Run the Interactive Terminal Simulation (with Benchmark & Gantt Chart)
```bash
python multithreaded_system.py
```
*Outputs real-time Banker's safety state evaluations, memory partition allocations, Gantt chart, and comparative benchmark (1 Worker vs 2 Workers vs 4 Workers).*

### 2. Launch the Graphical User Interface (GUI) Visualizer
```bash
python gui_dashboard.py
```
*Opens an interactive visual dashboard featuring:*
- Live animated worker thread cards and task progress bars.
- Real-time Banker's algorithm resource allocation matrix and safe sequence detector.
- Memory partition status block visualization.
- Interactive Gantt chart canvas.
- Policy toggles (FCFS, SJF, Priority) and worker thread count selector.

### 3. Launch the Browser Workbench
From the project root, run:
```bash
python web\app.py
```
Open `http://localhost:5000` to view the report-based dashboard with populated Banker's allocation data, request safety checks, scheduling policies, and memory-fit results.
Use **Your example** in the top menu to enter custom resource totals, memory partitions, and task definitions. **Run all procedures** calculates the custom Banker's safety sequence, request checks, CPU schedule, and memory-fit allocations; **Sample example** returns to the unchanged report workload.

### 4. Compile and Run the C++ Implementation
On Linux (Ubuntu/Debian) or Windows MinGW:
```bash
g++ -std=c++17 multithreaded_scheduler.cpp -o multithreaded_scheduler -pthread
./multithreaded_scheduler
```

---

## 📂 Project Directory Structure

```
d:/Sumit/Codes/OS/mini_project/
│
├── multithreaded_system.py      # Python 3 complete multithreaded engine & benchmark
├── gui_dashboard.py             # Tkinter interactive GUI dashboard for faculty viva demo
├── multithreaded_scheduler.cpp  # Modern C++17 thread pool and Banker's implementation
├── web\app.py                   # Flask browser workbench
├── web\templates\index.html     # Resource, scheduling, and memory dashboard
├── PROJECT_REPORT.md            # Formal lab record document (JSPM RSCOE format)
└── README.md                    # Project documentation & execution guide
```

---

## 🧠 OS Syllabus Concepts Integrated

| Module in Mini Project | OS Practical Experiment | Key Functionality |
|:---|:---:|:---|
| **Multithreaded Worker Pool** | **Exp 9 & Exp 3** | Concurrent workers using `std::thread` / `threading.Thread` with mutexes and condition variables. |
| **CPU Scheduling Engine** | **Exp 2** | Pluggable policies: FCFS, Shortest Job First (SJF), and Priority Scheduling with Aging. |
| **Deadlock Avoidance** | **Exp 4** | Real-time Banker's Algorithm verifying $Need \le Available$ and finding Safe Sequences. |
| **Contiguous Memory Manager**| **Exp 5** | Dynamic allocation using **Best Fit**, **First Fit**, and **Worst Fit** partition management. |
| **Performance Benchmark** | **CO1, CO2, CO3** | Computes Turnaround Time ($TAT$), Waiting Time ($WT$), Core Utilization (%), and Speedup ($1.8\times$). |

---

## 📊 Key Results Achieved
- **Speedup:** Achieved **$1.80\times$ speedup** over sequential execution.
- **Latency Reduction:** Average Turnaround Time reduced by **$44.5\%$**, and Average Waiting Time reduced by **$69.5\%$**.
- **Reliability:** $100\%$ deadlock-free operation through real-time Banker's safety verification.
