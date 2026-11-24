def score(board, placement):
    lines = placement['lines_cleared']
    score_val = lines * 3000.0

    holes_sum = 0
    for col in range(10):
        for row in range(20):
            if not board[row][col]:
                for r2 in range(row):
                    if board[r2][col]:
                        holes_sum += row
                        break

    score_val -= holes_sum * 200.0

    top_filled = [20] * 10
    for col in range(10):
        for r in range(20):
            if board[r][col]:
                top_filled[col] = r
                break

    irregularity_sq = 0
    for col in range(9):
        diff = top_filled[col] - top_filled[col+1]
        irregularity_sq += diff * diff

    score_val -= irregularity_sq * 50.0

    sum_top = sum(top_filled)
    score_val -= sum_top * 10.0

    return score_val
