namespace Kotor.NET.Patcher
{
    public class Memory : IMemory
    {
        private Dictionary<int, string> twodaMemory = new();
        private Dictionary<int, int> tlkMemory = new();

        public string? From2DAToken(int tokenID)
        {
            return twodaMemory.SingleOrDefault(x => x.Key == tokenID).Value;
        }

        public int? FromTLKToken(int tokenID)
        {
            return tlkMemory.Keys.Contains(tokenID) ? tlkMemory[tokenID] : null;
        }

        public void Set2DAToken(int tokenID, string value)
        {
            twodaMemory[tokenID] = value;
        }

        public void SetTLKToken(int tokenID, int value)
        {
            tlkMemory[tokenID] = value;
        }

        public void Clear()
        {
            twodaMemory.Clear();
            tlkMemory.Clear();
        }
    }
}
