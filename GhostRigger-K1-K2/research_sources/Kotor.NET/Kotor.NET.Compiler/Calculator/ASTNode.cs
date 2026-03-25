using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorNCS;

namespace Kotor.NET.Scripting.Calculator
{
    public interface ASTNode
    {
        void Compile(SymbolTable symbolTable, NCS ncs);
    }
}
