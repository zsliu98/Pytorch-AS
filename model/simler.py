import torch
import torch.nn as nn
import torch.nn.functional as func


class Simler(nn.Module):

    def __init__(self, negative_size, threshold):
        super(Simler, self).__init__()
        self.similarity = nn.CosineSimilarity(dim=1, eps=1e-8)
        self.negative_size = negative_size
        self.threshold = threshold
        self.pool = nn.MaxPool1d(kernel_size=self.negative_size)

    def forward(self, q, pa, na):
        if self.training:
            return self._train(q, pa, na)
        else:
            return self._evaluate(q, pa, na)

    def _train(self, q, pa, na):
        pa_sim = self.similarity(q, pa)
        if not hasattr(torch.Tensor, 'repeat_interleave'):
            na_sim = torch.zeros(q.shape[0])
            if torch.cuda.is_available():
                na_sim = na_sim.cuda()
            for i in range(q.shape[0]):
                temp = na[i * self.negative_size: (i + 1) * self.negative_size]
                temp = self.similarity(q[i].repeat(self.negative_size, 1), temp)
                na_sim[i] = temp.max()
        else:
            q_repeat = q.repeat_interleave(self.negative_size, 0)
            na_sim = self.similarity(q_repeat, na)
            na_sim = na_sim.view((1, 1, na_sim.shape[0]))
            na_sim = self.pool(na_sim)
            na_sim = na_sim.view((na_sim.shape[2]))
        if torch.cuda.is_available():
            loss = (torch.ones(q.shape[0]) * self.threshold).cuda() - pa_sim + na_sim
        else:
            loss = torch.ones(q.shape[0]) * self.threshold - pa_sim + na_sim
        return loss.mean(), (pa_sim.mean() - na_sim.mean()) / 2

    def _evaluate(self, q, pa, na):
        loss, _ = self._train(q, pa, na)
        accu = 0
        pa_sim = self.similarity(q, pa)
        for i in range(q.shape[0]):
            temp = na[i * self.negative_size: (i + 1) * self.negative_size]
            temp_sim = self.similarity(q[i].repeat(self.negative_size, 1), temp)
            temp_rank = torch.zeros_like(temp_sim)
            temp_rank[temp_sim > pa_sim[i]] = 1
            accu += 1 / (temp_rank.sum().item() + 1)
        return loss.item(), accu / q.shape[0]