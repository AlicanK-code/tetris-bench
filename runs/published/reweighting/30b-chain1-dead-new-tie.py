def score(board, placement):
    lines = placement["lines_cleared"]
    holes = 0
    for col in range(10):
        filled = False
        for row in range(20):
            if board[row][col]:
                filled = True
            elif filled:
                holes += 1
    heights = []
    for col in range(10):
        lowest_filled = -1
        for row in range(19, -1, -1):
            if board[row][col]:
                lowest_filled = row
                break
        if lowest_filled == -1:
            lowest_filled = 19
        heights.append(19 - lowest_filled)
    max_height = max(heights)
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(heights[i] - heights[i+1])
    unique_term = (placement["row"] * 10 + placement["column"]) * 0.001
    return lines * 10 - holes * 350 - max_height * 15 - bumpiness * 35 + unique_term
