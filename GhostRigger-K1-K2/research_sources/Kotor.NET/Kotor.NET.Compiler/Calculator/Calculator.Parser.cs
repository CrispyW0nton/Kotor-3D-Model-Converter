using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Kotor.NET.Scripting;
using Kotor.NET.Scripting.Compilation;

namespace Kotor.NET.Scripting.Calculator
{
    internal partial class CalculatorParser
    {
        public SymbolTable SymbolTable { get; set; }
        public CompilationUnit CompilationUnit { get; set; }
        public int test123 = 0;

        public CalculatorParser() : base(null)
        {


        }

        public void Parse(string s)
        {
            byte[] inputBuffer = System.Text.Encoding.Default.GetBytes(s);
            MemoryStream stream = new MemoryStream(inputBuffer);
            this.Scanner = new CalculatorScanner(stream);
            this.Parse();

            var xyz = this.ValueStack.Pop();
        }
    }
}
