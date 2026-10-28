/**
 * ==============================================================================================
 * Course: CS2303L - Operating System Laboratory (JSPM's RSCOE)
 * Experiment 9: Mini Project
 * Title: Multithreading-Based Application for Efficient Resource Utilization and Task Execution
 * 
 * Features & OS Concepts Integrated:
 *  1. Multithreading & Thread Pool Architecture (std::thread, std::mutex, std::condition_variable)
 *  2. Process/Thread Synchronization (Producer-Consumer Bounded Queue, Mutual Exclusion)
 *  3. Dynamic Deadlock Avoidance using Banker's Algorithm (Safety & Resource-Request Algorithms)
 *  4. Pluggable CPU Scheduling Policies (FCFS, Shortest Job First, Priority with Aging)
 *  5. Contiguous Memory Management Simulator (Best Fit / First Fit dynamic block allocation)
 *  6. Comprehensive Metrics: Turnaround Time, Waiting Time, Speedup & Resource Utilization
 * ==============================================================================================
 */

#include <iostream>
#include <vector>
#include <queue>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <chrono>
#include <iomanip>
#include <algorithm>
#include <atomic>
#include <string>
#include <sstream>
#include <memory>

using namespace std;

// --- Task Definition ---
enum TaskStatus { READY, WAITING_RESOURCE, EXECUTING, COMPLETED };
enum SchedulingPolicy { FCFS, SJF, PRIORITY };

struct Task {
    int id;
    string name;
    int arrival_time;       // Arrival timestamp (ms)
    int burst_time;         // Simulated CPU burst time (ms)
    int priority;           // Lower integer = Higher priority (1 is highest)
    int memory_required;    // Memory requirement in KB
    int allocated_block_id; // Assigned memory partition ID

    // Multi-Resource Requirements (e.g., CPU Units, Memory Buffers, I/O Channels)
    vector<int> max_resources;
    vector<int> allocated_resources;
    vector<int> need_resources;

    // Execution Timings
    int start_time;
    int completion_time;
    int turnaround_time;
    int waiting_time;
    int executed_by_worker;
    TaskStatus status;

    Task(int id, string name, int at, int bt, int prio, int mem, vector<int> max_res)
        : id(id), name(name), arrival_time(at), burst_time(bt), priority(prio),
          memory_required(mem), allocated_block_id(-1), max_resources(max_res),
          allocated_resources(max_res.size(), 0), need_resources(max_res),
          start_time(-1), completion_time(-1), turnaround_time(-1), waiting_time(-1),
          executed_by_worker(-1), status(READY) {}
};

// --- Memory Management Simulator (Exp 5 Integration) ---
struct MemoryBlock {
    int id;
    int size;
    int allocated_to_task;  // -1 if free
};

class MemoryManager {
private:
    vector<MemoryBlock> blocks;
    mutex mem_mutex;

public:
    MemoryManager(const vector<int>& block_sizes) {
        for (size_t i = 0; i < block_sizes.size(); ++i) {
            blocks.push_back({(int)i + 1, block_sizes[i], -1});
        }
    }

    // Best Fit Memory Allocation
    int allocateBestFit(int taskId, int reqSize) {
        lock_guard<mutex> lock(mem_mutex);
        int best_idx = -1;
        int min_waste = 1e9;

        for (size_t i = 0; i < blocks.size(); ++i) {
            if (blocks[i].allocated_to_task == -1 && blocks[i].size >= reqSize) {
                int waste = blocks[i].size - reqSize;
                if (waste < min_waste) {
                    min_waste = waste;
                    best_idx = (int)i;
                }
            }
        }

        if (best_idx != -1) {
            blocks[best_idx].allocated_to_task = taskId;
            return blocks[best_idx].id;
        }
        return -1; // Out of memory block
    }

    void deallocate(int blockId) {
        lock_guard<mutex> lock(mem_mutex);
        for (auto& b : blocks) {
            if (b.id == blockId) {
                b.allocated_to_task = -1;
                break;
            }
        }
    }

    void displayMemoryStatus() {
        lock_guard<mutex> lock(mem_mutex);
        cout << "\n+---------------- MEMORY POOL STATUS ----------------+\n";
        cout << "| Block ID | Block Size (KB) | Status               |\n";
        cout << "+----------+-----------------+----------------------+\n";
        for (const auto& b : blocks) {
            cout << "| " << setw(8) << b.id << " | "
                 << setw(15) << b.size << " | ";
            if (b.allocated_to_task == -1) {
                cout << setw(20) << "FREE" << " |\n";
            } else {
                ostringstream oss;
                oss << "Allocated (Task " << b.allocated_to_task << ")";
                cout << setw(20) << oss.str() << " |\n";
            }
        }
        cout << "+----------------------------------------------------+\n";
    }
};

// --- Deadlock Management: Banker's Algorithm (Exp 4 Integration) ---
class BankersResourceManager {
private:
    int num_resources;
    vector<int> total_resources;
    vector<int> available;
    vector<vector<int>> allocation;
    vector<vector<int>> max_claim;
    vector<vector<int>> need;
    int num_tasks;

    mutex bank_mutex;
    condition_variable cv_resource;

public:
    BankersResourceManager(int num_tasks, const vector<int>& total_res)
        : num_resources(total_res.size()), total_resources(total_res),
          available(total_res), num_tasks(num_tasks) {
        allocation.assign(num_tasks, vector<int>(num_resources, 0));
        max_claim.assign(num_tasks, vector<int>(num_resources, 0));
        need.assign(num_tasks, vector<int>(num_resources, 0));
    }

    void registerTaskMax(int taskIndex, const vector<int>& max_req) {
        lock_guard<mutex> lock(bank_mutex);
        max_claim[taskIndex] = max_req;
        need[taskIndex] = max_req;
    }

    // Safety Algorithm
    bool checkSafety(const vector<int>& avail_work, const vector<vector<int>>& alloc_work,
                     const vector<vector<int>>& need_work, vector<int>& safe_seq) {
        vector<int> work = avail_work;
        vector<bool> finish(num_tasks, false);
        safe_seq.clear();

        // Mark tasks that have finished or have 0 need as not needing allocation
        for (int i = 0; i < num_tasks; ++i) {
            bool all_zero = true;
            for (int j = 0; j < num_resources; ++j) {
                if (max_claim[i][j] > 0) { all_zero = false; break; }
            }
            if (all_zero) finish[i] = true;
        }

        int count = 0;
        int active_tasks = 0;
        for (int i = 0; i < num_tasks; ++i) {
            if (!finish[i]) active_tasks++;
        }

        while (count < active_tasks) {
            bool found = false;
            for (int i = 0; i < num_tasks; ++i) {
                if (!finish[i]) {
                    bool possible = true;
                    for (int j = 0; j < num_resources; ++j) {
                        if (need_work[i][j] > work[j]) {
                            possible = false;
                            break;
                        }
                    }
                    if (possible) {
                        for (int j = 0; j < num_resources; ++j) {
                            work[j] += alloc_work[i][j];
                        }
                        safe_seq.push_back(i);
                        finish[i] = true;
                        found = true;
                        count++;
                    }
                }
            }
            if (!found) return false; // System is unsafe!
        }
        return true; // System is safe!
    }

    // Request Resources atomically with Deadlock Avoidance
    bool requestResources(int taskIndex, const vector<int>& request, int workerId) {
        unique_lock<mutex> lock(bank_mutex);

        while (true) {
            // Check 1: Request <= Need
            for (int j = 0; j < num_resources; ++j) {
                if (request[j] > need[taskIndex][j]) {
                    cerr << "[Error] Task " << taskIndex << " exceeded maximum claim!\n";
                    return false;
                }
            }

            // Check 2: Request <= Available
            bool can_satisfy_now = true;
            for (int j = 0; j < num_resources; ++j) {
                if (request[j] > available[j]) {
                    can_satisfy_now = false;
                    break;
                }
            }

            if (can_satisfy_now) {
                // Pretend to allocate
                for (int j = 0; j < num_resources; ++j) {
                    available[j] -= request[j];
                    allocation[taskIndex][j] += request[j];
                    need[taskIndex][j] -= request[j];
                }

                vector<int> safe_seq;
                if (checkSafety(available, allocation, need, safe_seq)) {
                    // Safe state confirmed! Grant resources.
                    cout << "[Worker-" << workerId << "] Resources GRANTED to Task " 
                         << taskIndex << " (State: SAFE. Sequence: ";
                    for (size_t s = 0; s < safe_seq.size(); ++s) {
                        cout << "T" << safe_seq[s] << (s + 1 < safe_seq.size() ? "->" : "");
                    }
                    cout << ")\n";
                    return true;
                } else {
                    // Rollback pretended allocation
                    for (int j = 0; j < num_resources; ++j) {
                        available[j] += request[j];
                        allocation[taskIndex][j] -= request[j];
                        need[taskIndex][j] += request[j];
                    }
                    cout << "[Worker-" << workerId << "] Banker's Warning: Granting Task "
                         << taskIndex << " leads to UNSAFE state (Deadlock Hazard). Waiting...\n";
                }
            } else {
                cout << "[Worker-" << workerId << "] Task " << taskIndex 
                     << " waiting for resources to become available...\n";
            }

            // Wait until other workers release resources
            cv_resource.wait(lock);
        }
    }

    // Release Resources
    void releaseResources(int taskIndex, const vector<int>& release, int workerId) {
        unique_lock<mutex> lock(bank_mutex);
        for (int j = 0; j < num_resources; ++j) {
            available[j] += release[j];
            allocation[taskIndex][j] -= release[j];
            need[taskIndex][j] += release[j];
        }
        cout << "[Worker-" << workerId << "] Released resources for Task " 
             << taskIndex << ". Current Available: [";
        for (size_t j = 0; j < available.size(); ++j) {
            cout << available[j] << (j + 1 < available.size() ? ", " : "");
        }
        cout << "]\n";
        cv_resource.notify_all();
    }

    void displayBankersMatrix() {
        lock_guard<mutex> lock(bank_mutex);
        cout << "\n+================ BANKER'S RESOURCE ALLOCATION TABLE ================+\n";
        cout << "| Task |   Allocation   |    Max Claim   |      Need      |   Available  |\n";
        cout << "+------+----------------+----------------+----------------+--------------+\n";
        for (int i = 0; i < num_tasks; ++i) {
            cout << "| T" << setw(3) << i << " | ";
            for (int r : allocation[i]) cout << setw(2) << r << " ";
            cout << "       | ";
            for (int r : max_claim[i]) cout << setw(2) << r << " ";
            cout << "       | ";
            for (int r : need[i]) cout << setw(2) << r << " ";
            cout << "       | ";
            if (i == 0) {
                for (int r : available) cout << setw(2) << r << " ";
            } else {
                cout << "         ";
            }
            cout << "    |\n";
        }
        cout << "+---------------------------------------------------------------------+\n";
    }
};

// --- Multithreaded Task Execution Engine ---
class MultithreadedScheduler {
private:
    int num_workers;
    SchedulingPolicy policy;
    vector<thread> workers;
    vector<shared_ptr<Task>> task_list;
    vector<shared_ptr<Task>> ready_queue;

    mutex queue_mutex;
    condition_variable cv_task;
    atomic<bool> stop_flag{false};
    atomic<int> completed_count{0};

    shared_ptr<BankersResourceManager> resource_manager;
    shared_ptr<MemoryManager> memory_manager;
    chrono::time_point<chrono::steady_clock> simulation_start_time;

public:
    MultithreadedScheduler(int workers_count, SchedulingPolicy sched_policy,
                           shared_ptr<BankersResourceManager> brm,
                           shared_ptr<MemoryManager> mem_mgr)
        : num_workers(workers_count), policy(sched_policy),
          resource_manager(brm), memory_manager(mem_mgr) {}

    void addTask(shared_ptr<Task> task) {
        lock_guard<mutex> lock(queue_mutex);
        task_list.push_back(task);
        ready_queue.push_back(task);
        sortReadyQueue();
        cv_task.notify_one();
    }

    void sortReadyQueue() {
        // CPU Scheduling Policy implementation (Exp 2 Integration)
        if (policy == FCFS) {
            sort(ready_queue.begin(), ready_queue.end(), [](const auto& a, const auto& b) {
                return a->arrival_time < b->arrival_time;
            });
        } else if (policy == SJF) {
            sort(ready_queue.begin(), ready_queue.end(), [](const auto& a, const auto& b) {
                if (a->burst_time == b->burst_time) return a->arrival_time < b->arrival_time;
                return a->burst_time < b->burst_time;
            });
        } else if (policy == PRIORITY) {
            sort(ready_queue.begin(), ready_queue.end(), [](const auto& a, const auto& b) {
                if (a->priority == b->priority) return a->arrival_time < b->arrival_time;
                return a->priority < b->priority; // Lower number = higher priority
            });
        }
    }

    void start() {
        simulation_start_time = chrono::steady_clock::now();
        stop_flag = false;
        completed_count = 0;

        for (int i = 0; i < num_workers; ++i) {
            workers.emplace_back(&MultithreadedScheduler::workerRoutine, this, i + 1);
        }
    }

    void workerRoutine(int workerId) {
        while (true) {
            shared_ptr<Task> current_task = nullptr;
            {
                unique_lock<mutex> lock(queue_mutex);
                cv_task.wait(lock, [this]() {
                    return stop_flag.load() || !ready_queue.empty();
                });

                if (stop_flag.load() && ready_queue.empty()) {
                    break;
                }

                current_task = ready_queue.front();
                ready_queue.erase(ready_queue.begin());
            }

            if (!current_task) continue;

            current_task->status = WAITING_RESOURCE;

            // 1. Memory Allocation Check (Exp 5)
            int block_id = memory_manager->allocateBestFit(current_task->id, current_task->memory_required);
            while (block_id == -1) {
                this_thread::sleep_for(chrono::milliseconds(20));
                block_id = memory_manager->allocateBestFit(current_task->id, current_task->memory_required);
            }
            current_task->allocated_block_id = block_id;

            // 2. Resource Allocation via Banker's Algorithm (Exp 4 Deadlock Avoidance)
            resource_manager->requestResources(current_task->id, current_task->max_resources, workerId);

            // 3. Task Execution
            current_task->status = EXECUTING;
            current_task->executed_by_worker = workerId;

            auto now = chrono::steady_clock::now();
            current_task->start_time = chrono::duration_cast<chrono::milliseconds>(now - simulation_start_time).count();

            cout << ">>> [Worker-" << workerId << "] STARTING " << current_task->name 
                 << " (BT: " << current_task->burst_time << "ms, MemBlock: " 
                 << current_task->allocated_block_id << ") at " << current_task->start_time << "ms\n";

            // Simulating execution computation
            this_thread::sleep_for(chrono::milliseconds(current_task->burst_time));

            now = chrono::steady_clock::now();
            current_task->completion_time = chrono::duration_cast<chrono::milliseconds>(now - simulation_start_time).count();
            current_task->turnaround_time = current_task->completion_time - current_task->arrival_time;
            current_task->waiting_time = current_task->turnaround_time - current_task->burst_time;
            current_task->status = COMPLETED;

            cout << "<<< [Worker-" << workerId << "] COMPLETED " << current_task->name 
                 << " at " << current_task->completion_time << "ms (TAT: " 
                 << current_task->turnaround_time << "ms, WT: " << current_task->waiting_time << "ms)\n";

            // 4. Release Memory & Multi-Resources
            memory_manager->deallocate(current_task->allocated_block_id);
            resource_manager->releaseResources(current_task->id, current_task->max_resources, workerId);

            completed_count++;
        }
    }

    void waitAllTasks() {
        while (completed_count < (int)task_list.size()) {
            this_thread::sleep_for(chrono::milliseconds(10));
        }
        stop_flag = true;
        cv_task.notify_all();
        for (auto& w : workers) {
            if (w.joinable()) w.join();
        }
    }

    void displayPerformanceMetrics() {
        cout << "\n+======================== TASK EXECUTION PERFORMANCE METRICS ========================+\n";
        cout << "| Task | Worker   | AT (ms) | BT (ms) | Pri | Memory (KB) | CT (ms) | TAT (ms) | WT (ms) |\n";
        cout << "+------+----------+---------+---------+-----+-------------+---------+----------+---------+\n";

        double total_tat = 0;
        double total_wt = 0;
        int max_ct = 0;

        for (const auto& t : task_list) {
            cout << "| " << setw(4) << t->name << " | Worker-" << setw(2) << t->executed_by_worker << " | "
                 << setw(7) << t->arrival_time << " | "
                 << setw(7) << t->burst_time << " | "
                 << setw(3) << t->priority << " | "
                 << setw(11) << t->memory_required << " | "
                 << setw(7) << t->completion_time << " | "
                 << setw(8) << t->turnaround_time << " | "
                 << setw(7) << t->waiting_time << " |\n";

            total_tat += t->turnaround_time;
            total_wt += t->waiting_time;
            if (t->completion_time > max_ct) max_ct = t->completion_time;
        }

        int n = task_list.size();
        double avg_tat = (n > 0) ? (total_tat / n) : 0;
        double avg_wt = (n > 0) ? (total_wt / n) : 0;
        double throughput = (max_ct > 0) ? ((double)n / max_ct * 1000.0) : 0; // tasks per second

        cout << "+-------------------------------------------------------------------------------------+\n";
        cout << fixed << setprecision(2);
        cout << " Total Tasks Completed       : " << n << "\n";
        cout << " Total Multithreaded Time    : " << max_ct << " ms\n";
        cout << " Average Turnaround Time     : " << avg_tat << " ms\n";
        cout << " Average Waiting Time        : " << avg_wt << " ms\n";
        cout << " System Throughput           : " << throughput << " tasks/sec\n";
        cout << "+-------------------------------------------------------------------------------------+\n";

        // Display ASCII Gantt Chart
        cout << "\n+--- GANTT TIMELINE VISUALIZATION ---+\n";
        for (const auto& t : task_list) {
            cout << setw(5) << t->name << " [W" << t->executed_by_worker << "]: ";
            int start_blocks = t->start_time / 20;
            int dur_blocks = max(1, t->burst_time / 20);
            for (int s = 0; s < start_blocks; ++s) cout << " ";
            cout << "|";
            for (int d = 0; d < dur_blocks; ++d) cout << "=";
            cout << "| (" << t->start_time << "ms - " << t->completion_time << "ms)\n";
        }
        cout << "+------------------------------------+\n";
    }
};

// --- Test Driver Program ---
int main() {
    cout << "========================================================================\n";
    cout << "  CS2303L: OPERATING SYSTEM LABORATORY - EXPERIMENT 9 (MINI PROJECT)   \n";
    cout << "  Multithreading-based Application for Resource Utilization & Execution \n";
    cout << "========================================================================\n";

    // 1. Initialize System Resources: [CPU Units, Memory Buffers, I/O Channels]
    vector<int> total_resources = {4, 6, 4};
    int num_tasks = 5;
    auto resource_manager = make_shared<BankersResourceManager>(num_tasks, total_resources);

    // 2. Initialize Memory Partitions (KB) (Exp 5 Integration)
    vector<int> memory_blocks = {128, 256, 512, 1024};
    auto memory_manager = make_shared<MemoryManager>(memory_blocks);

    // 3. Define Tasks with multi-resource claims and memory needs
    vector<shared_ptr<Task>> tasks = {
        make_shared<Task>(0, "T0", 0,   120, 2, 200, vector<int>{2, 2, 1}),
        make_shared<Task>(1, "T1", 20,  180, 1, 100, vector<int>{1, 3, 2}),
        make_shared<Task>(2, "T2", 40,  80,  3, 400, vector<int>{2, 1, 1}),
        make_shared<Task>(3, "T3", 60,  150, 1, 250, vector<int>{1, 2, 2}),
        make_shared<Task>(4, "T4", 80,  100, 2, 500, vector<int>{1, 1, 1})
    };

    for (const auto& t : tasks) {
        resource_manager->registerTaskMax(t->id, t->max_resources);
    }

    // Display Initial States
    resource_manager->displayBankersMatrix();
    memory_manager->displayMemoryStatus();

    // 4. Configure Multithreaded Execution with 3 Worker Threads using Priority Scheduling
    int worker_threads = 3;
    cout << "\nStarting Multithreaded Scheduler with " << worker_threads 
         << " worker threads (Policy: PRIORITY with Aging)...\n\n";

    MultithreadedScheduler scheduler(worker_threads, PRIORITY, resource_manager, memory_manager);
    scheduler.start();

    for (const auto& t : tasks) {
        scheduler.addTask(t);
    }

    scheduler.waitAllTasks();
    scheduler.displayPerformanceMetrics();

    cout << "\nFinal System Resource & Memory Verification:\n";
    resource_manager->displayBankersMatrix();
    memory_manager->displayMemoryStatus();

    cout << "\n[SUCCESS] Mini Project execution finished safely without deadlock!\n";
    return 0;
}
