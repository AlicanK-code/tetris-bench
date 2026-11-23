def score(board, placement):
    lines = placement["lines_cleared"]
    sum_top = 0
    for j in range(10):
        for i in range(20):
            if board[i][j]:
                sum_top += i
                break
    holes = 0
    for j in range(10):
        found_filled = False
        for i in range(20):
            if board[i][j]:
                found_filled = True
            elif found_filled:
                holes += 1
    base_score = 1000 * lines - 10 * sum_top - 5 * holes
    return base_score + placement["rotation"] * 0.01 + placement["column"] * 0.001
