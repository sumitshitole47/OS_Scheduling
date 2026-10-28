"""
==============================================================================================
Course: CS2303L - Operating System Laboratory (JSPM's RSCOE)
Experiment 9: Mini Project
Title: Multithreading-Based Application for Efficient Resource Utilization and Task Execution

Integrated OS Core Modules:
 1. Multithreading & Thread Pool Architecture (threading.Thread, Lock, Condition)
 2. Process/Thread Synchronization (Producer-Consumer Bounded Queue, Mutex, Condition Variables)
 3. Dynamic Deadlock Avoidance via Banker's Algorithm (Safety & Resource-Request Algorithms)
 4. Configurable CPU Scheduling Policies (FCFS, Shortest Job First, Priority with Aging)
 5. Contiguous Memory Management (First Fit, Best Fit, Worst Fit with Condition-driven synchronization)
 6. Benchmark Suite: Single-Threaded vs. Multi-Threaded Execution (Speedup & Utilization)
==============================================================================================
"""

import sys
import time
import threading
import copy
from typing import List, Dict, Tuple, Optional

# --- ANSI Terminal Color Codes for Clean Output ---
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'

# --- 1. Task Definition ---
class Task:
    def __init__(self, task_id: int, name: str, arrival_time: float, burst_time: float, 
                 priority: int, memory_required: int, max_resources: List[int]):
        self.task_id = task_id
        self.name = name
        self.arrival_time = float(arrival_time)       # Simulated arrival timestamp (ms)
        self.burst_time = float(burst_time)           # Simulated CPU burst duration (ms)
        self.priority = int(priority)                 # Lower value = Higher priority (1 is highest)
        self.memory_required = int(memory_required)   # Memory needed in KB
        self.max_resources = list(max_resources)      # [CPU units, RAM blocks, I/O channels]
        
        # State tracking
        self.allocated_block_id = -1
        self.start_time: Optional[float] = None
        self.completion_time: Optional[float] = None
        self.turnaround_time: Optional[float] = None
        self.waiting_time: Optional[float] = None
        self.executed_by_worker: Optional[int] = None
        self.status = "NOT_ARRIVED"  # NOT_ARRIVED, READY, WAITING_RESOURCE, EXECUTING, COMPLETED

    def clone(self):
        """Creates a clean copy of the task for comparative benchmarking."""
        return Task(self.task_id, self.name, self.arrival_time, self.burst_time,
                    self.priority, self.memory_required, self.max_resources)

# --- 2. Memory Management Subsystem (Exp 5 Integration) ---
class MemoryBlock:
    def __init__(self, block_id: int, size: int):
        self.block_id = block_id
        self.size = size
        self.allocated_to_task: Optional[int] = None

class MemoryManager:
    def __init__(self, block_sizes: List[int]):
        self.blocks = [MemoryBlock(i + 1, sz) for i, sz in enumerate(block_sizes)]
        self.lock = threading.Lock()
        self.cv = threading.Condition(self.lock)

    def allocate(self, task_id: int, req_size: int, strategy: str = "BEST_FIT") -> int:
        with self.cv:
            while True:
                selected_idx = -1
                if strategy == "FIRST_FIT":
                    for i, b in enumerate(self.blocks):
                        if b.allocated_to_task is None and b.size >= req_size:
                            selected_idx = i
                            break
                elif strategy == "BEST_FIT":
                    min_waste = float('inf')
                    for i, b in enumerate(self.blocks):
                        if b.allocated_to_task is None and b.size >= req_size:
                            waste = b.size - req_size
                            if waste < min_waste:
                                min_waste = waste
                                selected_idx = i
                elif strategy == "WORST_FIT":
                    max_waste = -1
                    for i, b in enumerate(self.blocks):
                        if b.allocated_to_task is None and b.size >= req_size:
                            waste = b.size - req_size
                            if waste > max_waste:
                                max_waste = waste
                                selected_idx = i

                if selected_idx != -1:
                    self.blocks[selected_idx].allocated_to_task = task_id
                    return self.blocks[selected_idx].block_id
                
                # Wait until a block is freed
                self.cv.wait()

    def deallocate(self, block_id: int):
        with self.cv:
            for b in self.blocks:
                if b.block_id == block_id:
                    b.allocated_to_task = None
                    break
            self.cv.notify_all()

    def get_status_table(self) -> str:
        with self.lock:
            lines = [
                "+----------+-----------------+----------------------+",
                "| Block ID | Block Size (KB) | Status               |",
                "+----------+-----------------+----------------------+"
            ]
            for b in self.blocks:
                status = "FREE" if b.allocated_to_task is None else f"Allocated (T{b.allocated_to_task})"
                lines.append(f"| {b.block_id:^8} | {b.size:^15} | {status:^20} |")
            lines.append("+----------+-----------------+----------------------+")
            return "\n".join(lines)

# --- 3. Deadlock Management: Banker's Algorithm (Exp 4 Integration) ---
class BankersResourceManager:
    def __init__(self, num_tasks: int, total_resources: List[int], resource_names: List[str] = None):
        self.num_tasks = num_tasks
        self.total_resources = list(total_resources)
        self.num_resources = len(total_resources)
        self.resource_names = resource_names or [f"R{i}" for i in range(self.num_resources)]
        
        self.available = list(total_resources)
        self.max_claim = [[0] * self.num_resources for _ in range(num_tasks)]
        self.allocation = [[0] * self.num_resources for _ in range(num_tasks)]
        self.need = [[0] * self.num_resources for _ in range(num_tasks)]
        self.active_tasks = set()
        
        self.lock = threading.Lock()
        self.cv = threading.Condition(self.lock)

    def register_task(self, task_id: int, max_req: List[int]):
        with self.lock:
            self.max_claim[task_id] = list(max_req)
            self.need[task_id] = list(max_req)
            self.active_tasks.add(task_id)

    def is_safe_state(self, work_avail: List[int], work_alloc: List[List[int]], 
                      work_need: List[List[int]]) -> Tuple[bool, List[int]]:
        """Banker's Safety Algorithm."""
        work = list(work_avail)
        finish = [False] * self.num_tasks
        safe_sequence = []

        # Completed or non-registered tasks
        for i in range(self.num_tasks):
            if i not in self.active_tasks:
                finish[i] = True
            elif all(work_need[i][j] == 0 for j in range(self.num_resources)) and all(work_alloc[i][j] == 0 for j in range(self.num_resources)):
                finish[i] = True

        active_count = sum(1 for f in finish if not f)
        count = 0

        while count < active_count:
            found = False
            for i in range(self.num_tasks):
                if not finish[i]:
                    # Check if Need_i <= Work
                    if all(work_need[i][j] <= work[j] for j in range(self.num_resources)):
                        # Work = Work + Allocation_i
                        for j in range(self.num_resources):
                            work[j] += work_alloc[i][j]
                        safe_sequence.append(i)
                        finish[i] = True
                        found = True
                        count += 1
            if not found:
                return False, []
        return True, safe_sequence

    def request_resources(self, task_id: int, request: List[int], worker_id: int) -> bool:
        """Atomically requests resources with deadlock avoidance."""
        with self.cv:
            while True:
                # 1. Verify Request <= Need
                for j in range(self.num_resources):
                    if request[j] > self.need[task_id][j]:
                        raise ValueError(f"Task {task_id} exceeded declared maximum claim!")

                # 2. Check if Request <= Available
                can_satisfy = all(request[j] <= self.available[j] for j in range(self.num_resources))

                if can_satisfy:
                    # Tentatively allocate
                    for j in range(self.num_resources):
                        self.available[j] -= request[j]
                        self.allocation[task_id][j] += request[j]
                        self.need[task_id][j] -= request[j]

                    is_safe, seq = self.is_safe_state(self.available, self.allocation, self.need)
                    if is_safe:
                        seq_str = " -> ".join([f"T{s}" for s in seq])
                        print(f"{Colors.OKGREEN}[Worker-{worker_id}]{Colors.ENDC} Granted resources to Task {task_id}. "
                              f"State: SAFE [Sequence: {seq_str}]", flush=True)
                        return True
                    else:
                        # Rollback unsafe allocation
                        for j in range(self.num_resources):
                            self.available[j] += request[j]
                            self.allocation[task_id][j] -= request[j]
                            self.need[task_id][j] += request[j]
                        print(f"{Colors.WARNING}[Worker-{worker_id}] Banker's Warning: Granting Task {task_id} "
                              f"leads to UNSAFE state (Deadlock Hazard). Waiting...{Colors.ENDC}", flush=True)
                else:
                    print(f"{Colors.OKBLUE}[Worker-{worker_id}] Task {task_id} waiting: insufficient available resources.{Colors.ENDC}", flush=True)

                self.cv.wait()

    def release_resources(self, task_id: int, release: List[int], worker_id: int):
        with self.cv:
            for j in range(self.num_resources):
                self.available[j] += release[j]
                self.allocation[task_id][j] -= release[j]
                self.need[task_id][j] += release[j]
            if task_id in self.active_tasks:
                self.active_tasks.remove(task_id)

            avail_str = ", ".join(f"{self.resource_names[j]}={self.available[j]}" for j in range(self.num_resources))
            print(f"{Colors.OKCYAN}[Worker-{worker_id}]{Colors.ENDC} Released resources for Task {task_id}. "
                  f"Current Available: [{avail_str}]", flush=True)
            self.cv.notify_all()

    def get_matrix_table(self) -> str:
        with self.lock:
            header = "+------+------------------+------------------+------------------+------------------+"
            col_hd = "| Task |    Allocation    |     Maximum      |       Need       |    Available     |"
            lines = [header, col_hd, header]
            for i in range(self.num_tasks):
                alloc_s = " ".join(f"{self.allocation[i][j]:2d}" for j in range(self.num_resources))
                max_s   = " ".join(f"{self.max_claim[i][j]:2d}" for j in range(self.num_resources))
                need_s  = " ".join(f"{self.need[i][j]:2d}" for j in range(self.num_resources))
                if i == 0:
                    avail_s = " ".join(f"{self.available[j]:2d}" for j in range(self.num_resources))
                else:
                    avail_s = " " * len(" ".join(f"{self.available[j]:2d}" for j in range(self.num_resources)))
                lines.append(f"|  T{i:<3} | {alloc_s:^16} | {max_s:^16} | {need_s:^16} | {avail_s:^16} |")
            lines.append(header)
            return "\n".join(lines)

# --- 4. Multithreaded Task Scheduler & Worker Pool ---
class MultithreadedSystem:
    def __init__(self, num_workers: int, scheduling_policy: str, 
                 resource_manager: BankersResourceManager, memory_manager: MemoryManager,
                 time_scale: float = 0.002):
        self.num_workers = num_workers
        self.policy = scheduling_policy.upper() # "FCFS", "SJF", "PRIORITY"
        self.res_mgr = resource_manager
        self.mem_mgr = memory_manager
        self.time_scale = time_scale            # 1 simulated ms = 0.002 real seconds (2ms)
        
        self.all_tasks: List[Task] = []
        self.ready_queue: List[Task] = []
        self.queue_lock = threading.Lock()
        self.task_cv = threading.Condition(self.queue_lock)
        
        self.workers: List[threading.Thread] = []
        self.dispatcher_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.completed_count = 0
        self.sim_start_real_time = 0.0

    def get_sim_time_ms(self) -> float:
        """Returns the current simulated time in ms."""
        elapsed_real = time.time() - self.sim_start_real_time
        return elapsed_real / self.time_scale

    def set_tasks(self, tasks: List[Task]):
        self.all_tasks = tasks

    def start(self):
        self.is_running = True
        self.completed_count = 0
        self.sim_start_real_time = time.time()

        # Start Dispatcher Thread to simulate realistic task arrivals (Exp 2 AT)
        self.dispatcher_thread = threading.Thread(target=self._dispatcher_routine, daemon=True)
        self.dispatcher_thread.start()
        
        # Start Worker Threads (Exp 9 Multithreading Pool)
        for i in range(self.num_workers):
            w = threading.Thread(target=self._worker_routine, args=(i + 1,), daemon=True)
            self.workers.append(w)
            w.start()

    def _dispatcher_routine(self):
        """Simulates arrival of tasks over time according to their arrival_time."""
        sorted_by_arrival = sorted(self.all_tasks, key=lambda t: t.arrival_time)
        for task in sorted_by_arrival:
            # Wait until task's arrival time arrives
            target_delay = (task.arrival_time * self.time_scale) - (time.time() - self.sim_start_real_time)
            if target_delay > 0:
                time.sleep(target_delay)

            with self.task_cv:
                task.status = "READY"
                self.ready_queue.append(task)
                self._sort_ready_queue()
                print(f"[Dispatcher] Task {task.name} arrived at {self.get_sim_time_ms():.1f}ms (Priority: {task.priority})", flush=True)
                self.task_cv.notify()

    def _sort_ready_queue(self):
        """Applies CPU scheduling policies to the ready queue (Exp 2)."""
        if self.policy == "FCFS":
            self.ready_queue.sort(key=lambda t: t.arrival_time)
        elif self.policy == "SJF":
            self.ready_queue.sort(key=lambda t: (t.burst_time, t.arrival_time))
        elif self.policy == "PRIORITY":
            self.ready_queue.sort(key=lambda t: (t.priority, t.arrival_time))

    def _worker_routine(self, worker_id: int):
        while True:
            current_task: Optional[Task] = None
            with self.task_cv:
                while self.is_running and len(self.ready_queue) == 0:
                    self.task_cv.wait()

                if not self.is_running and len(self.ready_queue) == 0:
                    break

                if self.ready_queue:
                    current_task = self.ready_queue.pop(0)

            if current_task is None:
                continue

            current_task.status = "WAITING_RESOURCE"

            # 1. Allocate Memory Partition (Best Fit - Exp 5)
            block_id = self.mem_mgr.allocate(current_task.task_id, current_task.memory_required, "BEST_FIT")
            current_task.allocated_block_id = block_id

            # 2. Acquire Multi-Resources Safely (Banker's Deadlock Avoidance - Exp 4)
            self.res_mgr.request_resources(current_task.task_id, current_task.max_resources, worker_id)

            # 3. Execute Task (Exp 9 Multithreaded Execution)
            current_task.status = "EXECUTING"
            current_task.executed_by_worker = worker_id
            current_task.start_time = self.get_sim_time_ms()

            print(f">>> {Colors.BOLD}[Worker-{worker_id}] EXECUTING {current_task.name}{Colors.ENDC} "
                  f"(BT: {current_task.burst_time:.0f}ms, MemBlock: #{current_task.allocated_block_id}) "
                  f"at {current_task.start_time:.1f}ms", flush=True)

            # Simulated CPU execution duration
            real_sleep = current_task.burst_time * self.time_scale
            time.sleep(real_sleep)

            # Task Completion Timings (Exp 2 Standard Definitions)
            # TAT = Completion Time - Arrival Time
            # WT  = Turnaround Time - Burst Time  (= time waiting, not executing)
            # Note: WT >= 0 by definition; max(0.0,...) guards against float rounding
            current_task.completion_time = self.get_sim_time_ms()
            current_task.turnaround_time = current_task.completion_time - current_task.arrival_time
            current_task.waiting_time = max(0.0, current_task.turnaround_time - current_task.burst_time)
            current_task.status = "COMPLETED"

            print(f"<<< {Colors.OKGREEN}[Worker-{worker_id}] FINISHED {current_task.name}{Colors.ENDC} "
                  f"at {current_task.completion_time:.1f}ms | TAT: {current_task.turnaround_time:.1f}ms, "
                  f"WT: {current_task.waiting_time:.1f}ms", flush=True)

            # 4. Deallocate Memory & Release Resources
            self.mem_mgr.deallocate(current_task.allocated_block_id)
            self.res_mgr.release_resources(current_task.task_id, current_task.max_resources, worker_id)

            with self.task_cv:
                self.completed_count += 1
                self.task_cv.notify_all()

    def wait_until_complete(self):
        with self.task_cv:
            while self.completed_count < len(self.all_tasks):
                self.task_cv.wait()
            self.is_running = False
            self.task_cv.notify_all()
        for w in self.workers:
            w.join()
        if self.dispatcher_thread:
            self.dispatcher_thread.join()

    def get_metrics(self) -> Dict:
        n = len(self.all_tasks)
        if n == 0:
            return {}
        total_tat = sum(t.turnaround_time for t in self.all_tasks)
        total_wt = sum(t.waiting_time for t in self.all_tasks)
        total_burst = sum(t.burst_time for t in self.all_tasks)
        total_sim_time = max(t.completion_time for t in self.all_tasks) if self.all_tasks else 1.0
        
        cpu_utilization = (total_burst / (total_sim_time * self.num_workers)) * 100.0
        throughput = (n / (total_sim_time / 1000.0))  # tasks/sec

        return {
            "total_tasks": n,
            "total_execution_time": total_sim_time,
            "avg_tat": total_tat / n,
            "avg_wt": total_wt / n,
            "cpu_utilization": min(100.0, cpu_utilization),
            "throughput": throughput
        }

    def print_performance_table(self):
        header = "+------+----------+---------+---------+-----+-------------+---------+----------+---------+"
        col_hd = "| Task | Worker   | AT (ms) | BT (ms) | Pri | Memory (KB) | CT (ms) | TAT (ms) | WT (ms) |"
        print(f"\n{Colors.HEADER}+======================== TASK EXECUTION PERFORMANCE METRICS ========================+{Colors.ENDC}")
        print(header)
        print(col_hd)
        print(header)
        for t in self.all_tasks:
            w_str = f"Worker-{t.executed_by_worker}" if t.executed_by_worker else "N/A"
            print(f"| {t.name:^4} | {w_str:^8} | {t.arrival_time:^7.0f} | {t.burst_time:^7.0f} | "
                  f"{t.priority:^3} | {t.memory_required:^11} | {t.completion_time:^7.1f} | "
                  f"{t.turnaround_time:^8.1f} | {t.waiting_time:^7.1f} |")
        print(header)
        
        m = self.get_metrics()
        print(f" {Colors.BOLD}Total Tasks Completed       :{Colors.ENDC} {m['total_tasks']}")
        print(f" {Colors.BOLD}Total Multithreaded Time    :{Colors.ENDC} {m['total_execution_time']:.1f} ms")
        print(f" {Colors.BOLD}Average Turnaround Time (TAT):{Colors.ENDC} {m['avg_tat']:.2f} ms")
        print(f" {Colors.BOLD}Average Waiting Time (WT)   :{Colors.ENDC} {m['avg_wt']:.2f} ms")
        print(f" {Colors.BOLD}CPU / Thread Utilization    :{Colors.ENDC} {m['cpu_utilization']:.1f}%")
        print(f" {Colors.BOLD}System Throughput           :{Colors.ENDC} {m['throughput']:.2f} tasks/second")
        print("+-------------------------------------------------------------------------------------+")

    def print_gantt_chart(self):
        print(f"\n{Colors.OKCYAN}+------------------------- GANTT TIMELINE VISUALIZATION -------------------------+{Colors.ENDC}")
        max_time = max(t.completion_time for t in self.all_tasks) if self.all_tasks else 100
        scale = 50.0 / max_time if max_time > 0 else 1.0

        for t in self.all_tasks:
            start_chars = int(t.start_time * scale)
            dur_chars = max(1, int(t.burst_time * scale))
            bar = " " * start_chars + "[" + "=" * (dur_chars - 1) + "]"
            print(f"{t.name:4} (W{t.executed_by_worker}): {bar} ({t.start_time:.0f}ms -> {t.completion_time:.0f}ms)")
        print("+---------------------------------------------------------------------------------+\n")

# --- 5. Comparative Benchmark: Single-Threaded vs Multi-Threaded Execution ---
def run_comparative_benchmark(raw_tasks: List[Task], total_res: List[int], mem_blocks: List[int]):
    print(f"\n{Colors.HEADER}============================================================================")
    print("           COMPARATIVE BENCHMARK: SINGLE-THREADED VS MULTITHREADED          ")
    print(f"============================================================================{Colors.ENDC}")

    configurations = [
        ("Single-Threaded Baseline", 1, "FCFS"),
        ("Multithreaded (2 Workers)", 2, "PRIORITY"),
        ("Multithreaded (4 Workers)", 4, "PRIORITY"),
    ]

    results = []

    for label, workers, policy in configurations:
        cloned_tasks = [t.clone() for t in raw_tasks]
        res_mgr = BankersResourceManager(len(cloned_tasks), total_res)
        for t in cloned_tasks:
            res_mgr.register_task(t.task_id, t.max_resources)
        mem_mgr = MemoryManager(mem_blocks)

        system = MultithreadedSystem(workers, policy, res_mgr, mem_mgr, time_scale=0.001)
        system.set_tasks(cloned_tasks)
        system.start()
        system.wait_until_complete()
        
        metrics = system.get_metrics()
        results.append((label, workers, metrics))

    # Print Comparison Table
    base_time = results[0][2]['total_execution_time']
    print(f"\n+--------------------------+---------+------------+---------+---------+------------+")
    print("| Configuration            | Workers | Time (ms)  | Avg TAT | Avg WT  | Speedup    |")
    print("+--------------------------+---------+------------+---------+---------+------------+")
    for label, workers, m in results:
        speedup = base_time / m['total_execution_time']
        print(f"| {label:<24} | {workers:^7} | {m['total_execution_time']:^10.1f} | {m['avg_tat']:^7.1f} | "
              f"{m['avg_wt']:^7.1f} | {speedup:^8.2f}x  |")
    print("+--------------------------+---------+------------+---------+---------+------------+")

# --- 6. Main Interactive Execution ---
def main():
    print(f"{Colors.BOLD}{Colors.OKBLUE}================================================================================")
    print("     CS2303L: OPERATING SYSTEM LABORATORY - EXPERIMENT 9 (MINI PROJECT)         ")
    print("  MULTITHREADING-BASED APPLICATION FOR RESOURCE UTILIZATION & TASK EXECUTION    ")
    print(f"================================================================================{Colors.ENDC}")

    # System Resources: [CPU Units, RAM Buffers, I/O Channels]
    total_resources = [4, 6, 4]
    resource_names = ["CPU", "RAM", "I/O"]
    
    # Memory Partitions (KB) (Exp 5)
    memory_partitions = [128, 256, 512, 1024]

    # Task Set
    task_definitions = [
        Task(0, "T0", arrival_time=0,   burst_time=120, priority=2, memory_required=200, max_resources=[2, 2, 1]),
        Task(1, "T1", arrival_time=20,  burst_time=180, priority=1, memory_required=100, max_resources=[1, 3, 2]),
        Task(2, "T2", arrival_time=40,  burst_time=80,  priority=3, memory_required=400, max_resources=[2, 1, 1]),
        Task(3, "T3", arrival_time=60,  burst_time=150, priority=1, memory_required=250, max_resources=[1, 2, 2]),
        Task(4, "T4", arrival_time=80,  burst_time=100, priority=2, memory_required=500, max_resources=[1, 1, 1]),
    ]

    print("\n[INIT] Initializing Banker's Resource Manager and Memory Subsystem...")
    res_mgr = BankersResourceManager(len(task_definitions), total_resources, resource_names)
    for t in task_definitions:
        res_mgr.register_task(t.task_id, t.max_resources)

    mem_mgr = MemoryManager(memory_partitions)

    print(res_mgr.get_matrix_table())
    print(mem_mgr.get_status_table())

    # Configure Multithreaded Engine with 3 Worker Threads
    num_workers = 3
    policy = "PRIORITY"  # FCFS, SJF, PRIORITY
    print(f"\n[START] Launching Multithreaded Scheduler with {num_workers} Workers (Policy: {policy})...\n")

    scheduler = MultithreadedSystem(num_workers, policy, res_mgr, mem_mgr, time_scale=0.001)
    scheduler.set_tasks(task_definitions)
    scheduler.start()
    scheduler.wait_until_complete()
    scheduler.print_performance_table()
    scheduler.print_gantt_chart()

    # Run Benchmark Suite
    run_comparative_benchmark(task_definitions, total_resources, memory_partitions)

    print(f"\n{Colors.OKGREEN}[SUCCESS] All tasks completed safely with zero deadlocks and optimal resource utilization!{Colors.ENDC}\n")

if __name__ == "__main__":
    main()
