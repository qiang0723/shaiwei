import type { DomainStatus } from "./types";

export interface OperationsStatusCopy {
  title: string;
  detail: string;
  tone: "positive" | "warning" | "negative" | "neutral";
}

export function dataVerdictCopy(status: DomainStatus): OperationsStatusCopy {
  if (status === "PASS") {
    return {
      title: "数据门通过，可进入已冻结的信号流程",
      detail: "S1—S10 均处于允许状态；这是数据使用结论，不是策略有效性结论。",
      tone: "positive"
    };
  }
  if (status === "FAIL") {
    return {
      title: "数据门失败，当前信号流程必须阻断",
      detail: "至少一个日增量或哨兵硬门未通过；不得沿用旧数据或继续生成新信号。",
      tone: "negative"
    };
  }
  if (status === "WARN") {
    return {
      title: "数据门存在警告，需先核对再使用",
      detail: "当前证据包含非阻断警告；不得把警告状态简化为已完全通过。",
      tone: "warning"
    };
  }
  return {
    title: "数据证据尚未形成可用结论",
    detail: "当前状态不授权生成新信号；等待已登记日增量与哨兵证据形成完整终态。",
    tone: "neutral"
  };
}

export function systemCoreCopy(status: DomainStatus): OperationsStatusCopy {
  if (status === "PASS") {
    return {
      title: "核心闭环已完成，当前未发现失败恢复",
      detail: "全部必需阶段形成可用终态；这不替代页面外的实时容器检查。",
      tone: "positive"
    };
  }
  if (status === "WARN") {
    return {
      title: "核心闭环最终完成，但失败恢复历史仍在",
      detail: "最终状态可用，先前失败和恢复证据继续保留。",
      tone: "warning"
    };
  }
  if (status === "FAIL") {
    return {
      title: "核心闭环仍处于失败，当前结果不可交付",
      detail: "至少一个必需阶段终态失败；必须先处理阻断并形成新的受控证据。",
      tone: "negative"
    };
  }
  return {
    title: "核心闭环尚未形成完整终态",
    detail: "至少一个必需阶段尚未就绪；页面不把缺失证据推断成通过或失败恢复。",
    tone: "neutral"
  };
}

export function notificationCopy(status: DomainStatus): OperationsStatusCopy {
  if (status === "PASS") {
    return {
      title: "通知投递已完成",
      detail: "当前可寻址消息没有登记失败 attempt。",
      tone: "positive"
    };
  }
  if (status === "WARN") {
    return {
      title: "通知曾失败或恢复，重复投递风险仍须保留",
      detail: "通知状态独立于核心任务，最终送达不会删除失败 attempt。",
      tone: "warning"
    };
  }
  if (status === "FAIL") {
    return {
      title: "通知投递失败",
      detail: "核心任务结论不因此改写，但守护通道需要单独处理。",
      tone: "negative"
    };
  }
  return {
    title: "当日通知证据尚未就绪",
    detail: "没有足够的可寻址投递记录时，不推断消息已送达。",
    tone: "neutral"
  };
}
